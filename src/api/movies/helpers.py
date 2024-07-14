import requests
from requests.exceptions import JSONDecodeError

from flask_restx import abort
from flask_restx.fields import MarshallingError

from .models import CharacterModel, PlanetModel
from .exceptions import DataParserNotFound, NoResourceValue, WrongUrlResourceNotFound, RESOURCE_DOES_NOT_EXIST_MESSAGE
from .serializers import character_fetcher_serializer, planet_fetcher_serializer
from .route import api

from database import get_first, get_or_create

BASE_URL = "https://swapi.dev/api/"


def data_request(resource=None, url=None):
    if not url:
        if not resource:
            raise NoResourceValue("If not url provided, then resource parameter must be defined")
        url = f"{BASE_URL}{resource}/"
    try:
        return requests.get(url).json()
    except JSONDecodeError:
        raise WrongUrlResourceNotFound


def data_parser(object_dict, object_model, object_serializer, **kwargs):
    try:
        validated_data = api.marshal(object_dict, object_serializer, **kwargs)
        get_or_create(object_model, **validated_data)
    except MarshallingError:
        pass


def planet_data_parser(data):
    for planet_object in data:
        planet_object_dict = {
            "name": planet_object.get("name"),
            "diameter": planet_object.get("diameter") if planet_object.get("diameter") != "unknown" else None,
            "population": planet_object.get("population") if planet_object.get("population") != "unknown" else None,
            "terrain": planet_object.get("terrain") if planet_object.get("terrain") != "unknown" else None
        }
        data_parser(planet_object_dict, PlanetModel, planet_fetcher_serializer, skip_none=True)


def character_data_parser(data):
    for character_object in data:
        try:
            home_planet_name = data_request(url=character_object["homeworld"])["name"]
            related_planet_object = get_first(PlanetModel, name=home_planet_name)
            if not related_planet_object:
                raise NoResourceValue(f"Planet object with related name '{home_planet_name}' not found")
            character_object_dict = {
                "name": character_object.get("name"),
                "planet_id": related_planet_object.id
            }
            data_parser(character_object_dict, CharacterModel, character_fetcher_serializer)
        except NoResourceValue:
            continue


def request_page_data_parser(resource_type: str) -> None:
    data = data_request(resource=resource_type)
    next_page = data.get("next")
    if resource_type == "planets":
        data_type_parser = planet_data_parser
    elif resource_type == "people":
        data_type_parser = character_data_parser
    else:
        raise DataParserNotFound(
            "Data parser for related resource type was not found, make sure that this resource type is supported")
    data_type_parser(data["results"])
    while next_page:
        data = data_request(url=next_page)
        data_type_parser(data["results"])
        next_page = data.get("next")


def check_name_unique(model, attr_key, attr_value):
    planet_name_exist = None
    if attr_key == "name":
        planet_name_exist = get_first(model, name=attr_value)
    return True if planet_name_exist else False
