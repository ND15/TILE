import json
import logging
from typing import List, Dict
from utils.model import Skill, Task
from v3.utils.model import Skill

"""
Since the number of tasks will be exponential, it will be better to group them into tasks.
"""


class SkillLibrary:
    skills: list[Skill]

    def __init__(self, skill_json: str):
        self.skill_json = skill_json
        self.logger = logging.getLogger(__name__)

    def load_skill_json(self):
        try:
            with open(self.skill_json, 'r') as f:
                skills = json.load(f)
        except FileNotFoundError as e:
            print(f"Error in loading skill library")

    def load_skills(self, skills):
        self.skills = [
            Skill(name=skill.name,
                  description=skill.description,
                  code=skill.code,
                  package_dependencies=skill.package_dependencies,
                  function_dependencies=skill.function_dependencies,
                  created_at=skill.created_at,
                  success_count=skill.code,
                  failure_count=skill.failure_count,
                  average_execution_time=skill.average_execution_time) for skill in skills]

    def find_matching_skill(self, task: Task) -> Skill:
        pass