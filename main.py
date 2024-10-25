import ollama
import logging
from taskplanner import TaskPlanner
from reflection import Reflection
from action import TaskExecutor

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    planner = TaskPlanner('mistral-nemo')
    executor = TaskExecutor()

    user_query = "Generate a animation of the word Pallavi with 1s and 0s like in the Matrix Movie"

    tasks = planner.generate_plan(user_query)
    task_list = planner.make_tasks_list(tasks)

    response = executor.execute_task_list(task_list)

    logging.info(f"{user_query} Executed Successfully")
    logging.info(f"{response}")
