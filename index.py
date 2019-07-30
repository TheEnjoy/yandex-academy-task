import configparser
import logging
import os
from collections import defaultdict
from multiprocessing import Lock
from typing import Tuple

from flask import Flask, request
from jsonschema.exceptions import ValidationError
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from pymongo.results import InsertOneResult
from werkzeug.exceptions import BadRequest

from data_validator import DataValidator


def make_app(db: MongoClient, data_validator: DataValidator) -> Flask:
    app = Flask(__name__)

    def make_error_response(message: str, status_code: int) -> Tuple[dict, int]:
        app.logger.error(message)
        return {'message': message}, status_code

    locks = defaultdict(Lock)

    @app.route('/imports', methods=['POST'])
    def imports():

        if not request.is_json:
            return make_error_response('Content-Type must be application/json', 400)

        try:
            import_data = request.get_json()
            data_validator.validate_import(import_data)

            with locks['post_imports']:
                import_id = db['imports'].count()
                import_data['import_id'] = import_id

                db_response: InsertOneResult = db['imports'].insert_one(import_data)
                if db_response.acknowledged:
                    response = {'data': {'import_id': import_id}}
                    return response, 201
                else:
                    return make_error_response('Operation was not acknowledged', 400)
        except ValidationError as e:
            return make_error_response('Import data is not valid: ' + str(e), 400)
        except BadRequest as e:
            return make_error_response('Error when parsing JSON: ' + str(e), 400)
        except PyMongoError as e:
            return make_error_response('Database error: ' + str(e), 400)
        except Exception as e:
            return make_error_response(str(e), 400)

    @app.route('/imports/<int:import_id>/citizens/<int:citizen_id>', methods=['PATCH'])
    def citizen(import_id: int, citizen_id: int):
        if not request.is_json:
            return make_error_response('Content-Type must be application/json', 400)

        try:
            patch_data = request.get_json()
            data_validator.validate_citizen_patch(patch_data)

            update_data = {
                '$set': {f'citizens.$.{key}': val for key, val in patch_data.items()}
            }
            projection = {
                '_id': 0,
                'import_id': 0,
                'citizens': {
                    '$elemMatch': {'citizen_id': citizen_id}
                }
            }
            db_response: dict = db['imports'].find_one_and_update(
                filter={'import_id': import_id, 'citizens.citizen_id': citizen_id}, update=update_data,
                projection=projection, return_document=ReturnDocument.AFTER)
            if db_response is None:
                return make_error_response('Import or citizen with specified id not found', 400)

            return {'data': db_response['citizens'][0]}, 201
        except ValidationError as e:
            return make_error_response('Citizen patch is not valid: ' + str(e), 400)
        except BadRequest as e:
            return make_error_response('Error when parsing JSON: ' + str(e), 400)
        except PyMongoError as e:
            return make_error_response('Database error: ' + str(e), 400)
        except Exception as e:
            return make_error_response(str(e), 400)

    return app


def main():
    logging.basicConfig(filename='logs/service.log')

    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.cfg')
    config.read(config_path)
    db_uri = config['DATABASE']['DATABASE_URI']
    db_name = config['DATABASE']['DATABASE_NAME']

    db = MongoClient(db_uri)[db_name]
    data_validator = DataValidator()
    app = make_app(db, data_validator)
    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
