from abc import ABC, abstractmethod
import numpy as np

from models.frame import Frame


class BaseFrameSource(ABC):
    """
    Abstract interface for all frame sources.

    Every frame source must implement the same API
    so it can be swapped without changing the pipeline.
    """

    @abstractmethod
    def read(self) -> Frame:
        """
        Return the next frame.
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """
        Release allocated resources.
        """
        pass
    
    def reset(self) -> None:
        pass