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

## Question from Data B about this:

Quick reframe/question that may simplify the contract: 
can we just pull "freshest pose" instead of streaming it?

We're pulling frames from Embedded on demand, not streaming them, and
pretty worried about CPU-only performance. Since we only want the pose
data for frames we're going to process, subscribing to a 50 Hz pose
stream means handling a lot more data than we'll use and running a
queue subscription we don't need. We'd propose a slight refactoring of
how Data-B gets pose data, depending on what Embedded is already going
to be doing with it:

* Option 1: Embedded provides it. If Embedded already has pose
in-process (Data A co-located, or used for closed-loop control etc), a
single call returns (frame, pose, frame_stamp_ms, pose_stamp_ms). No
extra processing for anyone.

* Option 2:  We query Data-A directly. If Embedded doesn't already
access pose data, we'd just call Data-A directly at capture time
rather than route pose through Embedded just to hand it to us. Then we
don't push it to Embedded just to hand it to Data-B.

Two questions to resolve this:

* Embedded: Are you already accessing pose data?
* Data A: Do you support a synchronous "give me the freshest pose now"
call, or is 50 Hz pub/sub the only access pattern?

## Response from Data-A:

 Short version: yes — Data A supports a synchronous "freshest pose now" call; 50 Hz pub/sub is not the only access pattern. Our control loop already holds the
  current pose, so freshest-pose-on-demand is just a different door on the same state. It's implemented, verified, and now merged to main, so rather than fight
  the calendar let's settle any remaining details async.

  Merged contract + reference code (pinned to the merge commit):
  - pose helpers: https://github.com/KamaTechOrg/robo-greeno-data-a/blob/1a42122/interfaces/pose_publisher.py
  - the contract: https://github.com/KamaTechOrg/robo-greeno-data-a/blob/1a42122/interfaces/INTEGRATION.md
  - discussion/history: https://github.com/KamaTechOrg/robo-greeno-data-a/pull/4

  What's in it:
  - Data A side: --serve answers freshest-pose over MQTT request/reply (<topic>/get -> reply on a per-frame reply_topic); co-located callers import
  get_latest_pose() (no broker at all).
  - Data B side: request_latest_pose(host, port, topic, timeout_ms=100) and a --get CLI — so you can build the client against it today, no robot needed.
  - Verified end-to-end: the reply is a schema-valid pose_stamped, the freshest pose advances between calls, and a missing server returns None on timeout.

  On your two options — the deciding fact is pose ownership:
  - Embedded owns the raw sensors (camera frames). Data A owns pose — it's the one process holding the latest. Embedded does not inherently have pose; I
  confirmed with Dosithee that Embedded is open-loop servo control, no pose in-process.
  - So Option 2 (c) is the default: Data B pulls pose from Data A directly at capture time. Embedded keeps grabbing frames on demand and touches no pose — zero
  new work for them.
  - Option 1 (a) only pays off if we co-locate Data A's estimator inside Embedded's process (then the grabber stamps frame+pose in one call, zero skew). Worth
  doing later, especially if locomotion goes closed-loop — not required now.
  - Either way we avoid routing pose Data A -> Embedded -> Data B just to relay it.

  The timing guarantee: we bind pose to the frame's capture instant via the shared epoch-ms clock and reject the pair if the two stamps differ by more than ~50
  ms. This is a sampling problem, not a freshness one — pose sampled at capture means the seconds of CPU inference latency cancel out exactly, because the
  (frame, pose) pair was frozen before inference ran. The Δt gate is a simultaneity check on the two samples, and it only carries meaning because frame and pose
  share the one Pi clock. We'll keep the 50 Hz publisher up for Cloud + replay, but Data B doesn't subscribe.

  Two related notes from the Embedded thread:
  - Dosithee offered to move servo control to ESP32 + PCA9685 so the Pi is dedicated to camera/inference. I'd recommend taking that — it frees Pi CPU for your
  vision work, the same constraint you raised. (Follow-on: ESP32 then needs its clock disciplined to the Pi, but frame stamping stays Pi-side so spatial tagging
  is unaffected.)
  - Open question for everyone: who provides the IMU on real hardware, and on which MCU? Data A's pose is kinematic dead-reckoning today (drifts without IMU).
