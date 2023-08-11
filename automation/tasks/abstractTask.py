from abc import ABC, abstractmethod

class AbstractTask(ABC):

    @abstractmethod
    def execute():
        pass