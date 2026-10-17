
import os
from collections import deque

class MyClass:
    def __init__(self, value):
        self.value = value
        self.data = []

    def add_data(self, item):
        self.data.append(item)

    def get_value(self):
        return self.value

def process_list(items):
    processed = [x * 2 for x in items if x > 0]
    return processed

if __name__ == "__main__":
    instance = MyClass(10)
    instance.add_data(5)
    print(f"Value: {instance.get_value()}")

    my_list = [1, -2, 3, 0, 4]
    result = process_list(my_list)
    print(f"Processed list: {result}")

    q = deque([1, 2, 3])
    q.append(4)
    print(f"Deque: {q}")
