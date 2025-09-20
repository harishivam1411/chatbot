import textwrap
from collections import OrderedDict

from app.templates.prompt import get_prompt

class ChatManage:
    def __init__(self):
        self.memory = OrderedDict()
        self.query_count = 0
        self.max_memory_size = 7

    def add_user_message(self, query: str):
        self.query_count += 1
        self.memory[f"User (query_num -> {self.query_count})"] = query

    def add_bot_message(self, response: str):
        self.memory[f"AI (response_num -> {self.query_count})"] = response
        self._manage_memory()

    def _manage_memory(self):
        if len(self.memory) > self.max_memory_size * 2:
            # Pop the first two items (oldest chat pairs)
            self.memory.popitem(last=False)  # Oldest user message
            self.memory.popitem(last=False)  # Oldest bot/MSP response
        self.get_history()

    def get_history(self):
        if not self.memory:
            return "No history found for the user, as they are just started their conversation."
        max_key_length = max(len(key) for key in self.memory)
        indent_space = max_key_length + 2
        history_str = ""

        for i, (key, value) in enumerate(self.memory.items()):
            wrapped = textwrap.fill(
                value,
                width=130,
                initial_indent=' ' * (max_key_length - len(key)) + f"{key}: ",
                subsequent_indent=' ' * indent_space
            )
            history_str += f"{wrapped}\n"
            # Add an extra newline after every 2 entries (a pair)
            if i % 2 == 1:
                history_str += '\n'
        # print(f"History str ---> {history_str}")
        return history_str

    def get_response_prompt(self, query, current_context, admission_status):
        history = self.get_history()
        query_count: int = self.query_count
        prompt = get_prompt(query, history, current_context, query_count, admission_status)
        return prompt