from abc import ABC, abstractmethod
import numpy as np


class BaseFrameSource(ABC):
    """
    Abstract interface for all frame sources.

    Every frame source must implement the same API
    so it can be swapped without changing the pipeline.
    """

    @abstractmethod
    def read(self) -> np.ndarray:
        """
        Return the next frame.

        Returns:
            np.ndarray:
                Frame in OpenCV format:
                (height, width, 3), dtype=uint8
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """
        Release allocated resources.
        """
        pass