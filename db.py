import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore_async
import os

db = None

def init_db(key_path):
    global db
    if not os.path.exists(key_path):
        print(f"ВНИМАНИЕ: Файл ключа Firebase {key_path} не найден!")
        print("Бот будет работать в режиме мок-базы, или упадет при запросах.")
        class MockDB:
            def __init__(self):
                self.data = {}

            def collection(self, name):
                return MockCollection(self.data, name)

        class MockCollection:
            def __init__(self, parent_dict, name):
                if name not in parent_dict:
                    parent_dict[name] = {}
                self.data = parent_dict[name]

            def document(self, name):
                return MockDocument(self.data, str(name))

            async def get(self):
                class MockDocStream:
                    def __init__(self, data):
                        self._data = data
                    def to_dict(self): return self._data

                results = []
                for doc_id, doc_data in self.data.items():
                    if '_data' in doc_data:
                        results.append(MockDocStream(doc_data['_data']))
                return results

            async def stream(self):
                class MockDocStream:
                    def __init__(self, data):
                        self._data = data
                    def to_dict(self): return self._data

                for doc_id, doc_data in self.data.items():
                    # Return only docs that actually have data (not just subcollections)
                    if '_data' in doc_data:
                        yield MockDocStream(doc_data['_data'])

        class MockDocument:
            def __init__(self, parent_dict, name):
                if name not in parent_dict:
                    parent_dict[name] = {}
                self.doc_node = parent_dict[name]

            def collection(self, name):
                if '_subcollections' not in self.doc_node:
                    self.doc_node['_subcollections'] = {}
                return MockCollection(self.doc_node['_subcollections'], name)

            async def get(self):
                class MockDocRes:
                    def __init__(self, exists, data=None):
                        self.exists = exists
                        self._data = data or {}
                    def to_dict(self): return self._data

                if '_data' in self.doc_node:
                    return MockDocRes(True, self.doc_node['_data'])
                return MockDocRes(False)

            async def set(self, data, merge=False):
                if merge and '_data' in self.doc_node:
                    self.doc_node['_data'].update(data)
                else:
                    self.doc_node['_data'] = data

            async def update(self, data):
                if '_data' in self.doc_node:
                    self.doc_node['_data'].update(data)
        db = MockDB()
        return db

    cred = credentials.Certificate(key_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore_async.client()
    return db

def get_db():
    return db
