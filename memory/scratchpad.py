class Scratchpad:
    def __init__(self):
        self.goal = ""
        self.plan = ""
        self.current_tool = ""
        self.state = ""

    def update(
        self,
        goal=None,
        plan=None,
        current_tool=None,
        state=None,
    ):
        if goal is not None:
            self.goal = goal

        if plan is not None:
            self.plan = plan

        if current_tool is not None:
            self.current_tool = current_tool

        if state is not None:
            self.state = state

    def get_context(self):
        return {
            "goal": self.goal,
            "plan": self.plan,
            "current_tool": self.current_tool,
            "state": self.state,
        }

    def clear(self):
        self.__init__()