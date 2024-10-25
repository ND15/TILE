import weaviate
import os
from typing import List, Dict, Tuple
from model import Skill
from weaviate.classes.config import Configure, Property, DataType


class VectorDatabase:
    def __init__(self, weaviate_host=None, weaviate_port=None, weaviate_grpc_host=None, weaviate_grpc_port=None):
        self.skill_id = 0
        self.weaviate_host = weaviate_host
        self.weaviate_port = weaviate_port
        self.weaviate_grpc_host = weaviate_grpc_host
        self.weaviate_grpc_port = weaviate_grpc_port

    def initialize_skill_library(self):
        client = weaviate.connect_to_custom(http_host=self.weaviate_host,
                                            http_port=self.weaviate_port,
                                            http_secure=True,
                                            grpc_host=self.weaviate_grpc_host,
                                            grpc_port=self.weaviate_grpc_port,
                                            grpc_secure=True)

        if not client.collections.exists("Skills"):
            """
            Skill:
                name: str
                description: str
                code: str
                package_dependencies: List[str]
                function_dependencies: List[str]
                created_at: datetime
                success_count: int = 0
                failure_count: int = 0
                average_execution_time: float = 0.0
                tags: List[str] = None
            """
            client.collections.create(
                "Skills",
                vectorizer_config=Configure.Vectorizer.text2vec_transformers(),
                properties=[
                    Property(name="skill_id", data_type=DataType.NUMBER),
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="descripton", data_type=DataType.TEXT),
                    Property(name="code", data_type=DataType.TEXT),
                    Property(name="package_dependencies", data_type=DataType.TEXT_ARRAY),
                    Property(name="function_dependencies", data_type=DataType.TEXT_ARRAY),
                    Property(name="created_at", data_type=DataType.DATE),
                    Property(name="success_count", data_type=DataType.NUMBER),
                    Property(name="failure_count", data_type=DataType.NUMBER),
                    Property(name="average_execution_time", data_type=DataType.NUMBER),
                    Property(name="tags", data_type=DataType.TEXT_ARRAY),
                ]
            )
            print("Skills object created")
        else:
            print("Skills object exists")

        client.close()

    def insert(self, skill: Skill):
        client = weaviate.connect_to_custom(http_host=self.weaviate_host, http_port=self.weaviate_port,
                                            http_secure=False,
                                            grpc_host=self.weaviate_grpc_host, grpc_port=self.weaviate_grpc_port,
                                            grpc_secure=False)
        SkillObject = client.collections.get("Skills")
        uuid = SkillObject.data.insert({
            "skill_id": self.skill_id,
            "name": skill.name,
            "description": skill.description,
            "code": skill.code,
            "package_dependencies": skill.package_dependencies,
            "function_dependencies": skill.function_dependencies,
            "created_at": skill.created_at,
            "success_count": skill.success_count,
            "failure_count": skill.failure_count,
            "average_execution_time": skill.average_execution_time,
            "tags": skill.tags
        })
        print("Skill inserted with uuid: ", uuid)
        self.skill_id += 1

    def search(self, msg, distance: int = 0.3):
        client = weaviate.connect_to_local(host=self.weaviate_host, port=self.weaviate_port)
        Question = client.collections.get("Skills")
        response = Question.query.near_text(
            query=msg,
            distance=distance
        )

        ids = [o.properties["skill_id"] for o in response.objects]
        print(ids)
        return list(map(int, ids))


if __name__ == "__main__":
    client = weaviate.connect_to_local(
        host="127.0.0.1",  # Use a string to specify the host
        port=8080,
        grpc_port=50051,
    )

    print(client.is_ready())
