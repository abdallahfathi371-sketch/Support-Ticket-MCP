import json
import os
from datetime import datetime


class SemanticMemory:

    def __init__(self, file_path=None):

        if file_path is None:

            base_dir = os.path.dirname(
                os.path.abspath(__file__)
            )

            file_path = os.path.join(
                base_dir,
                "semantic_memory.json"
            )

        self.file_path = file_path

        if not os.path.exists(self.file_path):

            with open(self.file_path, "w") as f:
                json.dump([], f)


    def load(self):

        with open(self.file_path, "r") as f:
            return json.load(f)


    def save(self, data):

        with open(self.file_path, "w") as f:
            json.dump(
                data,
                f,
                indent=4
            )


    def add_fact(self, subject, fact):

        memories = self.load()

        for item in memories:

            if item["subject"] == subject:

                item["history"].append({

                    "version": item["version"],

                    "fact": item["current_fact"],

                    "timestamp": item["last_updated"]

                })

                item["version"] += 1

                item["current_fact"] = fact

                item["last_updated"] = datetime.now().isoformat()

                self.save(memories)

                return


        memories.append({

            "subject": subject,

            "current_fact": fact,

            "version": 1,

            "history": [],

            "created_at": datetime.now().isoformat(),

            "last_updated": datetime.now().isoformat()

        })

        self.save(memories)


    def get_all(self):

        return self.load()


    def clear(self):

        self.save([])