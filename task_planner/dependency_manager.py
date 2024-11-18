import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
import networkx
import networkx as nx


@dataclass
class Task:
    id: int
    name: str
    description: str


@dataclass
class TaskNode:
    task: Task
    dependencies: Set[int] = field(default_factory=set)
    dependents: Set[int] = field(default_factory=set)
    status: str = "pending"


class DependencyManager:
    def __init__(self):
        self._graph = networkx.DiGraph()
        self.tasks: Dict[int, TaskNode] = {}

    def add_task(self, task: Task, dependencies: Optional[List[int]] = None):
        """
        Adds task to the tasks list and creates edge between the dependencies and the task.

        Args:
            task: Task class
            dependencies: List of dependencies of the task
        """
        if task.id in self.tasks:
            raise f"{task.id} already exists in the graph"

        node = TaskNode(task=task)
        self.tasks[task.id] = node
        self._graph.add_node(task.id)

        if dependencies:
            for dependency in dependencies:
                if dependency not in self.tasks:
                    raise f"Dependency {dependency} does not exists in the list"
                self.add_dependency(dependency, task.id)

    def add_dependency(self, dependency_id: int, dependent_id: int):
        """
        Adds dependency edge between dependency and dependent
        and checks for cycles
        """
        if dependency_id not in self.tasks or dependent_id not in self.tasks:
            raise ValueError("Both tasks must exist in the graph")

        self.tasks[dependency_id].dependents.add(dependent_id)
        self.tasks[dependent_id].dependencies.add(dependency_id)
        self._graph.add_edge(dependency_id, dependent_id)

        if not nx.is_directed_acyclic_graph(self._graph):
            self._graph.remove_edge(dependency_id, dependent_id)
            self.tasks[dependency_id].dependents.remove(dependent_id)
            self.tasks[dependent_id].dependencies.remove(dependency_id)
            raise ValueError("Adding this dependency would create a cycle")

    def mark_task(self, task_id: int, flag: str):  # replace with an enum
        if not self.tasks[task_id]:
            raise f"{task_id} does not exist in the graph"

        self.tasks[task_id].status = flag

    def get_completed_tasks(self):
        return [task for _, task in self.tasks.items() if task.status.lower() == "completed"]

    def get_failed_tasks(self):
        return [task for _, task in self.tasks.items() if task.status.lower() == "failed"]

    def get_pending_tasks(self):
        return [task for _, task in self.tasks.items() if task.status.lower() == "pending"]

    def get_available_tasks(self) -> list[tuple[int, Task]]:
        available_tasks = []
        for task_id, task in self.tasks.items():
            if task.status == 'pending' and all(
                    self.tasks[dependency] == "completed" for dependency in task.dependencies):
                available_tasks.append((task_id, task.task))
        return available_tasks

    def execution_graph(self) -> List[Task]:
        """
        Returns a linear ordering of the execution graph using Topological sort
        """
        try:
            task_ids = networkx.topological_sort(self._graph)
            return [self.tasks[task_id].task for task_id in task_ids]
        except Exception as e:
            raise f"Could not create an execution list, cycle may be present"

    def visualize_tasks(self):
        tasks: Dict[int, Dict] = {}
        for task_id in self.tasks:
            task_str = {
                "name": self.tasks[task_id].task.name,
                "dependencies": list(self.tasks[task_id].dependencies),
                "dependents": list(self.tasks[task_id].dependents),
                "status": self.tasks[task_id].status
            }
            tasks[task_id] = task_str

        with open("tasks.json", "w") as f:
            json.dump(tasks, f)

    def dependency_graph(self):
        print(self.tasks)
        tasks: Dict[int, Dict] = {}

        def recursive_builder(node, visited):
            if node not in visited:
                visited.add(node)
                task_info = {
                    "id": self.tasks[node].task.id,
                    "name": self.tasks[node].task.name,
                    "dependencies": list(self.tasks[node].dependencies),
                    # "dependents": list(self.tasks[node].dependents),
                    "status": self.tasks[node].status
                }

                children = [recursive_builder(node, visited) for node in self.tasks[node].dependents if
                            node not in visited]
                children = [child for child in children if child is not None]

                if children:
                    task_info["children"] = children
                return task_info
            return None

        dependency_hierarchy = {}
        hierarchy = recursive_builder(1, set())

        return hierarchy

# if __name__ == "__main__":
#     x = {
#         "Tasks": [
#             {
#                 "id": 1,
#                 "name": "generate_random_dependencies",
#                 "description": "Create a function that generates a random dependency list.  The function should take two arguments: `num_tasks` (integer, the total number of tasks) and `max_dependencies` (integer, the maximum number of dependencies a task can have).  The output should be a list of dictionaries, where each dictionary represents a task and has the format `{'id': task_id, 'dependencies': [list of dependency ids]}`. Ensure that dependencies are always valid (i.e., they refer to existing task IDs and don't create circular dependencies).  Use `random.sample` for generating random dependencies.",
#                 "dependencies": []
#             },
#             {
#                 "id": 2,
#                 "name": "convert_to_d3_format",
#                 "description": "Create a function that converts the dependency list generated in the previous step into a format suitable for D3.js. The output should be a dictionary with two keys: 'nodes' and 'links'.  'nodes' should be a list of dictionaries, where each dictionary represents a task and has the format `{'id': task_id}`. 'links' should be a list of dictionaries, where each dictionary represents a dependency and has the format `{'source': source_task_id, 'target': target_task_id}`.  Use list comprehensions and the dependency list from the previous step as input.",
#                 "dependencies": [1]
#             },
#             {
#                 "id": 3,
#                 "name": "create_d3_visualization_template",
#                 "description": "Create a basic HTML file containing a `<div>` element to hold the visualization and include the D3.js library.  This will serve as the template for embedding the visualization.  No Python code is required for this step; just create the HTML file manually.",
#                 "dependencies": []
#             },
#             {
#                 "id": 4,
#                 "name": "generate_d3_javascript_code",
#                 "description": "Create a function that takes the D3-formatted data (from step 2) and generates the JavaScript code required to create a force-directed graph visualization using D3.js. The generated code should append the SVG element to the `<div>` in the HTML template, create nodes and links based on the data, and implement a force simulation to layout the graph.  The function should return the complete JavaScript code as a string.",
#                 "dependencies": [2, 3]
#             },
#             {
#                 "id": 5,
#                 "name": "embed_javascript_in_html",
#                 "description": "Create a function that takes the HTML template (from step 3) and the generated JavaScript code (from step 4) and embeds the JavaScript within `<script>` tags in the HTML file.  The function should write the complete HTML with embedded JavaScript to a new file (e.g., 'd3_visualization.html').",
#                 "dependencies": [3, 4]
#             },
#             {
#                 "id": 6,
#                 "name": "combine_all_steps",
#                 "description": "Combine all the previous steps into a single Python program.  Generate random dependencies, convert them to the D3 format, generate the JavaScript code, embed it in the HTML template, and save the final HTML file.  The program should take `num_tasks` and `max_dependencies` as input from the user.",
#                 "dependencies": [1, 2, 4, 5]
#             }
#         ]
#     }
#
#     g = DependencyManager()
#     for task_data in x["Tasks"]:
#         task = Task(
#             id=int(task_data['id']),
#             name=task_data['name'],
#             description=task_data['description']
#         )
#         g.add_task(task, task_data["dependencies"])
#
#     hierarchy = g.dependency_graph()
#
#     with open("hierarchy.json", "w") as f:
#         json.dump(hierarchy, f)
