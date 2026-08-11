from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Task(BaseModel):
    """
    A single executable task in the decomposition DAG.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    instruction: str = Field(min_length=5)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """
    Validated task-decomposition plan represented as a DAG.
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=5)
    tasks: list[Task] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_dag(self) -> "Plan":
        # Task IDs must be unique.
        ids = [task.id for task in self.tasks]

        if len(ids) != len(set(ids)):
            raise ValueError("Task ids must be unique")

        known = set(ids)

        # Every dependency must reference an existing task.
        for task in self.tasks:
            missing = set(task.depends_on) - known

            if missing:
                raise ValueError(
                    f"{task.id} has unknown dependencies: {sorted(missing)}"
                )

            # A task cannot depend on itself.
            if task.id in task.depends_on:
                raise ValueError(
                    f"{task.id} cannot depend on itself"
                )

        # The dependency graph must be acyclic.
        if not nx.is_directed_acyclic_graph(self.graph):
            cycle = nx.find_cycle(self.graph)

            blocked = sorted(
                {
                    node
                    for edge in cycle
                    for node in edge[:2]
                }
            )

            raise ValueError(
                f"Cycle detected; blocked tasks: {blocked}"
            )

        return self

    @property
    def graph(self) -> nx.DiGraph:
        """
        Build the dependency graph.

        Edges are directed:

            dependency -> dependent task
        """

        graph = nx.DiGraph()

        graph.add_nodes_from(
            task.id for task in self.tasks
        )

        graph.add_edges_from(
            (dependency, task.id)
            for task in self.tasks
            for dependency in task.depends_on
        )

        return graph

    def topological_order(self) -> list[str]:
        """
        Return tasks in dependency-safe execution order.
        """

        return list(nx.topological_sort(self.graph))

    def execution_batches(self) -> list[list[str]]:
        """
        Return dependency-safe parallel execution batches.

        Tasks in the same batch have no unresolved dependencies
        between them.
        """

        return [
            sorted(generation)
            for generation in nx.topological_generations(self.graph)
        ]

    def task(self, task_id: str) -> Task:
        """
        Retrieve a task by ID.
        """

        return next(
            task
            for task in self.tasks
            if task.id == task_id
        )

    def terminal_tasks(self) -> list[str]:
        """
        Return tasks with no dependents.

        A valid decomposition should normally have
        exactly one terminal synthesis task.
        """

        return [
            node
            for node, degree in self.graph.out_degree
            if degree == 0
        ]


class Thought(BaseModel):
    """
    Candidate thought used by Tree-of-Thoughts / LATS style algorithms.
    """

    model_config = ConfigDict(extra="forbid")

    state: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class EnvironmentFeedback(BaseModel):
    """
    Grounded feedback produced outside the language model.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    score: float = Field(ge=0.0, le=1.0)
    details: list[str] = Field(default_factory=list)
