import json
import os
from datetime import datetime


class EpisodicMemory:

    def __init__(self, file_path=None):

        if file_path is None:

            base_dir = os.path.dirname(
                os.path.abspath(__file__)
            )

            file_path = os.path.join(
                base_dir,
                "episodic_memory.json"
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


    def add_episode(
        self,
        content,
        reason,
        importance=0.5
    ):

        episodes = self.load()

        episodes.append({

            "timestamp":
                datetime.now().isoformat(),

            "content":
                content,

            "reason":
                reason,

            "importance":
                importance

        })

        self.save(episodes)


    def get_all(self):

        return self.load()


    def clear(self):

        self.save([])