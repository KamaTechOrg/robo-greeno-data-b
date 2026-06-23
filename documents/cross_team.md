# Data-B Cross Team Integration Questions and Answers

## Embeddded Team:

Accelerator decision: Has a final decision been made to run inference on Raspberry Pi 5 CPU only, or should we integrate a hardware accelerator such as Hailo AI HAT+?
Image acquisition interface: How does the image capture code expose frames to the processing pipeline?
      Should our code pull frames on demand, or will frames be pushed to us via callback/queue/stream?
Could you please confirm the expected architecture for both points?[4:41 PM]Hi,

1. Accelerator Decision:
For now we are running on Raspberry Pi 3B CPU only — no hardware accelerator in this phase. Hailo AI HAT+ is not in our current BOM. If inference is too slow in Phase 3/4, we will revisit this. For now please optimize your models for RPi CPU.

2. Image Acquisition Interface:
The embedded team will use Pi Camera v2 via the RPi camera module. Frames will be pulled on demand by your code using OpenCV:

cap = cv2.VideoCapture(0)
ret, frame = cap.read()

We are not pushing frames via callback or stream at this stage. Your pipeline should pull frames on demand. If you need a queue-based architecture later, we can wrap it together in Phase 4.


## Data-A:

Status on your four questions

Validate queue architecture — Data A pose is an on-bot 50 Hz MQTT pub/sub side-channel (robogreeno/data-a/<robot_id>/pose, QoS 0), not part of your detection queue. Only a single pose snapshot rides each detection message into MQTT→Kafka→AgCloud, so your Kafka/Postgres path is unchanged. A monotonic seq field lets you detect drops/reorders.

Clarify payload schema — rigid, versioned JSON Schema (additionalProperties:false). You add 3 fields to each detection message — additive, nothing else changes:
"robot_id": "spider-01",
"pose": { "position_m": [x,y,z], "orientation_quat": [w,x,y,z] },
"pose_stamp_ms": 1781000130123
One change on your side: timestamp float-seconds → stamp_ms int (epoch ms) — which also matches AgCloud captured_ts, so Postgres ingest lines up.

Confirm async comm flow — stamp at capture, not publish. Carry the frame's capture stamp_ms; bind the pose at that instant via (a) Embedded stamping pose onto the frame (preferred, zero skew), or (b) nearest-stamp match from the 50 Hz stream (reject Δt > 50 ms). One clock, epoch-ms. This is what makes the seconds-long inference latency irrelevant.

Verify detector integration — the detector needs nothing from Data A at inference time (runs on the image alone). Data B owns camera intrinsics; Data A owns the camera→body extrinsic (fixed transform in the URDF). Optional: Data A can flag stable-stance instants (foot_contacts ≥ 3 + low angular_rps) to cut motion blur on the moving robot.
Contract (pinned to commit 259d31f so links can't drift)

Overview: https://github.com/KamaTechOrg/robo-greeno-data-a/blob/259d31f/interfaces/INTEGRATION.md
Schema: https://github.com/KamaTechOrg/robo-greeno-data-a/blob/259d31f/interfaces/pose_stamped.schema.json
Build against it today, no robot needed: https://github.com/KamaTechOrg/robo-greeno-data-a/blob/259d31f/interfaces/sample_pose_stream.jsonl (200 schema-valid messages) + https://github.com/KamaTechOrg/robo-greeno-data-a/blob/259d31f/interfaces/pose_publisher.py (--mqtt to live-publish at 50 Hz).
Addressed by KamaTechOrg/robo-greeno-data-a@259d31f (see interfaces/).

How Data A (hexapod locomotion) connects to the other Robo-Greeno tracks. This is Data A's side of the contract — a concrete proposal to align on, not a unilateral decision. It is built from what each team's repo actually does today (investigated 2026-06-22).

Embedded — KamaTechOrg/robogreeno-emb
Data B — KamaTechOrg/robo-greeno-data-b
Cloud — KamaTechOrg/robogreeno-cloud
Canonical platform — KamaTechOrg/AgCloud, KamaTechOrg/AgStream
0. Shared conventions (proposed, aligned to AgCloud)

The robot pipeline ultimately publishes to AgCloud, so Data A adopts AgCloud's canonical conventions rather than inventing new ones:

Concern	Convention	Why
Timestamp	epoch milliseconds, UTC (stamp_ms)	matches AgCloud captured_ts (ms). Data B and Cloud currently use float seconds — this is the one change we ask of them.
Body frame	+X forward, +Y left, +Z up (right-handed)	matches config.py and REP-103; unambiguous for IMU + pose.
Units	metres, radians, m/s, rad/s	SI throughout.
Orientation	unit quaternion [w, x, y, z]	no Euler ambiguity.
Geo (Cloud/AgCloud)	WGS84 lat/lon when a global fix exists	AgCloud telemetry.lat/lon. Indoors we use odom + node_id instead.
robot_id	stable string e.g. spider-01	same id everywhere (MQTT topics, messages).
The canonical message is pose_stamped.schema.json (see pose_stamped.example.json).

1. Data A ↔ Embedded — robot model & joint commands

What Data A provides: hexapod.urdf (generated from config.py) + servo_conventions.md: the 18-channel servo map, joint ranges, command format (18 absolute joint targets in rad at 50 Hz), and a PWM calibration template.

What Embedded provides back: servo feedback availability (open vs closed loop), confirmation the controller wiring follows channel order 0…17, and the filled PWM calibration table.

Status: Embedded repo is currently empty (README + CODEOWNERS only) — this is the Week-1 deliverable and the cleanest hand-off; nothing to reconcile yet.

2. Data A ↔ Data B — pose for spatial tagging of detections

Data B runs on-bot detection and publishes to MQTT topic MQTT/vision/detections (JSON: frame_id, timestamp, image_quality, detection.results[…] with pixel bbox). Their plan explicitly needs robot pose + IMU per frame to spatially tag detections (Sprint 4 / SLAM), and their Issue #11 "Data A Integration Questions" is open and unanswered.

Contract:

Time base. Camera frames and pose_stamped share one clock, in stamp_ms (epoch ms, UTC). On a single Pi this is the system clock; if IMU runs on the ESP32, Embedded disciplines it to the Pi clock. (Data B converts its current float-seconds timestamp → ms.)
Pose delivery — two options, recommend (a):
(a) Embedded stamps at capture (preferred): the frame grabber attaches the latest pose + stamp_ms to each frame before handing it to Data B. No clock-skew, no lookup. Data B copies the block into its detection JSON.
(b) Pose stream + nearest-time lookup (fallback): Data A publishes pose_stamped at ~50 Hz on robogreeno/data-a/<robot_id>/pose; Data B samples the pose whose stamp_ms is closest to the frame's stamp_ms (reject if Δt > 50 ms).
What Data B adds to each detection message (additive, non-breaking):
"robot_id": "spider-01",
"pose": { "...": "the pose_stamped 'pose' block" },
"pose_stamp_ms": 1781000130123
Detections stay in pixel coords; 3D back-projection (camera intrinsics + extrinsics) is deferred jointly — Data B owns intrinsics, Data A owns the camera→body extrinsic once the mount is fixed.
Answers to Data B Issue #11 (frame rate 50 Hz, same time domain yes, pose = position+quaternion in odom, formalize at Sprint 1) are posted to that issue.

3. Data A ↔ Cloud — odometry for collaborative mapping

Cloud is a DTN/swarm relay: carriers publish TelemetryMessage (spider_id, battery, storage_ratio, node_id, float-seconds timestamp) to robogreeno/carrier/<id>/telemetry. Position today is a greenhouse-graph node_id, not continuous pose; no mapping/fusion exists yet. The Wk-10 hand-off is Data A → Cloud relative-pose for collaborative mapping.

Contract:

Data A emits a slim odometry variant of pose_stamped sized for BLE/DTN (well under the 512 B budget) — drop imu, covariance6, joint_angles_rad:
{"schema":"robo-greeno/data-a/pose_stamped","version":1,"robot_id":"spider-01",
 "stamp_ms":1781000130123,"frame":"body","odom_frame":"odom",
 "pose":{"position_m":[3.142,-0.871,0.075],"orientation_quat":[0.995,0,0,0.098]},
 "node_id":"n12"}
Routing: carried as a new field/record alongside TelemetryMessage (same topic family), or a new pose message type — Cloud's call. node_id bridges Data A's continuous odom pose to Cloud's graph model so Cloud can fuse without immediately running SLAM.
Fusion ownership: Data A provides per-robot odometry (drifts over time, relative to power-on). Cloud owns multi-robot fusion / loop closure. Data A does not claim a global frame indoors.
Cloud's blocker first: Cloud Issue #14 (message serialization) must land before this flows end-to-end; the schema above is ready to slot in.

4. What this resolves

A single timestamp + frame convention across four repos that currently disagree (float-s vs ms; no agreed body frame).
Embedded's Week-1 unblock (URDF + servo map exist now).
A concrete answer to Data B's open Issue #11 and a pose block they can paste in.
A DTN-sized odometry message Cloud can ingest once their serialization lands.


