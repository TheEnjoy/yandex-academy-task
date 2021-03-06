import unittest
from datetime import datetime
from unittest.mock import MagicMock

from bson import json_util
from jsonschema import ValidationError

import tests.test_utils as test_utils


class ImportPostTests(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.app, cls.db, cls.validator = test_utils.set_up_service()

    def test_successful_import_post_should_return_import_id(self):
        headers = [('Content-Type', 'application/json')]
        import_data = test_utils.read_data('import.json')
        import_id = 0

        http_response = self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)

        response_data = http_response.get_json()
        import_data['import_id'] = import_id
        for citizen in import_data['citizens']:
            citizen['birth_date'] = datetime.strptime(citizen['birth_date'], '%d.%m.%Y')
        self.assertEqual(import_id, response_data['data']['import_id'])
        self.assertEqual(http_response.status_code, 201)
        self.assertEqual(import_data, self.db['imports'].find_one({'import_id': import_id}, {'_id': 0}))

    def test_import_id_should_increase_for_each_import(self):
        headers = [('Content-Type', 'application/json')]

        for import_id in range(2):
            import_data = test_utils.read_data('import.json')
            http_response = self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)

            response_data = http_response.get_json()
            import_data['import_id'] = import_id
            for citizen in import_data['citizens']:
                citizen['birth_date'] = datetime.strptime(citizen['birth_date'], '%d.%m.%Y')
            self.assertEqual(import_id, response_data['data']['import_id'])
            self.assertEqual(http_response.status_code, 201)
            self.assertEqual(import_data, self.db['imports'].find_one({'import_id': import_id}, {'_id': 0}))

    def test_when_no_content_type_should_return_bad_request(self):
        http_response = self.app.post('/imports', data=json_util.dumps({'test': 1}))

        response_data = http_response.get_data(as_text=True)
        self.assertIn('Content-Type must be application/json', response_data)
        self.assertEqual(400, http_response.status_code)

    def test_when_database_error_should_return_bad_request(self):
        headers = [('Content-Type', 'application/json')]
        import_data = {'_id': '5a8f1e368f7936badfbb0cfa', 'citizens': []}

        self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)
        http_response = self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)

        http_data = http_response.get_data(as_text=True)
        self.assertIn('Database error: ', http_data)
        self.assertEqual(400, http_response.status_code)

    def test_when_incorrect_json_should_return_bad_request(self):
        headers = [('Content-Type', 'application/json')]

        http_response = self.app.post('/imports', data='{', headers=headers)

        response_data = http_response.get_data(as_text=True)
        self.assertIn('Error when parsing JSON: ', response_data)
        self.assertEqual(400, http_response.status_code)

    def test_when_invalid_import_should_return_bad_request(self):
        headers = [('Content-Type', 'application/json')]
        mock_validation = MagicMock(side_effect=ValidationError('message'))
        with unittest.mock.patch.object(self.validator, 'validate_import', mock_validation):
            http_response = self.app.post('/imports', data=json_util.dumps({'test': 1}), headers=headers)

            response_data = http_response.get_data(as_text=True)
            self.assertIn('Input data is not valid', response_data)
            self.assertEqual(400, http_response.status_code)

    def test_should_return_bad_request_when_birth_date_wrong_format(self):
        headers = [('Content-Type', 'application/json')]
        import_data = {'citizens': [{'citizen_id': 0, 'birth_date': 'aaa'}]}

        self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)
        http_response = self.app.post('/imports', data=json_util.dumps(import_data), headers=headers)

        http_data = http_response.get_data(as_text=True)
        self.assertIn('does not match format', http_data)
        self.assertEqual(400, http_response.status_code)


if __name__ == '__main__':
    unittest.main()
