import time

import cv2
import numpy as np

from frame_source.base_frame_source import BaseFrameSource
from models.frame import Frame

class SyntheticSource(BaseFrameSource):
    """
    Synthetic frame generator for pipeline testing.

    Generates simple animated frames that simulate
    a live video stream without requiring real hardware.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        rectangle_speed: int = 5,
    ) -> None:
        self.width = width
        self.height = height
        self.rectangle_speed = rectangle_speed

        self.frame_count = 0
        self.rectangle_x = 0

    def read(self) -> np.ndarray:
        """
        Generate and return the next synthetic frame.
        """

        frame = np.zeros(
            (self.height, self.width, 3),
            dtype=np.uint8
        )

        rectangle_width = 100
        rectangle_height = 100

        start_point = (
            self.rectangle_x,
            150
        )

        end_point = (
            self.rectangle_x + rectangle_width,
            150 + rectangle_height
        )

        cv2.rectangle(
            frame,
            start_point,
            end_point,
            (0, 255, 0),
            thickness=-1
        )

        cv2.putText(
            frame,
            f"Frame: {self.frame_count}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Timestamp: {time.time():.2f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        self.rectangle_x += self.rectangle_speed

        if self.rectangle_x > self.width:
            self.rectangle_x = -rectangle_width

        self.frame_count += 1

        return Frame(
            image=frame,
            timestamp=time.time(),
            frame_id=self.frame_count,
            source="synthetic"
        )

    def release(self) -> None:
        """
        Release resources.
        """

        cv2.destroyAllWindows()