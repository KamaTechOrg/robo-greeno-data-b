# Robo-Greeno — Data Team B 10-Week Plan

5 phases, each a 2-week sprint. The dominant project-management strategy is **end-to-end-first with stubs, then iterative swap-in**: the whole pipeline runs by end of Sprint 2 with mock components everywhere, and each subsequent sprint replaces stubs with real components. This de-risks integration, surfaces interface bugs early, and means the project is *never* in a state where it can't be demoed.

## Working as a Scrum team

Each phase is a **2-week sprint** with a clearly stated **sprint goal**, a list of **sprint commits** (must-deliver), and a list of **backlog items** (negotiable scope, prioritized). The student team operates as a Scrum team; the OJT lead acts as effective Product Owner.

A few notes on running this as Scrum:

- **Sprint goal first, deliverables second.** The phase summary is the sprint goal — the *why*. Deliverables exist to serve the goal; if a deliverable doesn't move the goal forward, drop it.
- **Sprint commits vs backlog.** Each phase separates what the team commits to ship (sprint commits) from what would be nice to ship if time permits (backlog items, prioritized). When scope pressure hits, drop backlog items from the bottom up, in conversation with the PO. Don't drop sprint commits silently.
- **Definition of Done.** Each deliverable below has crisp acceptance criteria. "Done" means the criteria are met and another team member has reviewed; not "I wrote some code."
- **Cross-team checkpoints align with sprint boundaries.** Each phase's checkpoints surface at sprint review (end of phase) and feed into next sprint's planning.
- **Standalone labs are a separate track.** The "standalone lab for next cohort" deliverables are meta-products for the OJT program, not for the Robo-Greeno demo. They accumulate one per phase so they don't all land in the final week.
- **Retro prompts** at the bottom of each phase point at things worth surfacing in the sprint retrospective. Light touch, but explicit.
- **PO availability matters more here than for a seasoned team.** Backlog refinement is itself a learning skill for first-time Scrum participants; expect to be denser in PO involvement than a normal product setting would warrant.

## Project guardrails (cross-cutting)

**Project ethos: "use what already exists, optimize it for the edge."** The organizer has explicitly asked the team to lean on existing networks rather than train from scratch where possible. The KamaTechOrg/AgCloud project — built by previous cohorts — already provides the cloud-side ingestion (MQTT → Kafka → Flink/Airflow → storage), an existing leaf-pipeline in `airflow_bundle/`, and device simulators. The team's job is to plug into that, not replace it. Network optimization for embedded (quantization, format conversion, edge benchmarking) is the project's primary KPI; reasonable accuracy is a constraint, not the headline.

**Data-source progression:** **fake/synthetic → test cam → live cam → test robo data → live robo data.** Each phase moves at least one notch along this progression. The team is *never* blocked waiting for real spider/hexapod imagery — there's always a viable fallback further left on the chain — but they're *always* ready to swap in real data the moment it arrives.

**Detection ordering — fruit → pest → disease.** Fruit (easiest) builds momentum; pest (hardest) gets attacked while there's still slack; disease (moderate, plus the lab-to-field cross-eval methodology) lands at the end alongside demo prep. This intentionally orders against importance so schedule pressure falls on the easier-to-rescue tasks.

**Camera calibration is deferred** out of Phase 1 per organizer's instruction. It re-enters as a one-day spike whenever real cameras come online and need intrinsics for a specific task.

**Soil quality is committed in Phase 4**, no longer a stretch.

**Lab-to-field generalization gap is the project's central educational narrative**, measured in Phase 5's cross-eval. If only one chart appears in the final demo, this is it.

**About the AgCloud-experienced team member.** One team member contributed to AgCloud in a previous cohort. They are *not* a contributor on this project — treat them as a **consultable resource** with limited time: budget for 1–2 hour-long Q&A sessions plus async follow-up. The team owns its own AgCloud reading and integration work. The organizer has also offered to convene the previous cohort for additional questions; treat that as a second, more formal shot at institutional knowledge.

**Replan triggers.** Phase 1's findings may shift this plan — particularly if AgCloud's actual integration surface is more complex than expected, or if the embedded team's hardware timeline is much later or much earlier than assumed. The end-to-end-first philosophy is committed; specific phase boundaries are not.

---

## Sprint 1 — Foundations, Existing-Work Audit, and Tooling
**Weeks 1–2 (Phase 1)**

**Sprint goal:** Establish the project's contracts, conventions, and shared knowledge — so that Sprint 2 can stub the entire pipeline cleanly and Sprint 3 can swap in real components without rework.

This sprint has two equally important goals: (1) *understand what already exists* (AgCloud, pretrained ag models, available datasets) before building anything new, and (2) **define the interface contracts** at every boundary the pipeline will need (image source → IQA → detector → JSON → MQTT → AgCloud), enabling clean stub-then-swap downstream.

**Required reading**
- KamaTechOrg/AgCloud README plus self-guided walkthrough of `mqtt_and_kafka/`, `storage_with_mqtt/`, `simulators/`, and `airflow_bundle/leaf-pipeline/`. Leave Week 1 knowing: (a) what MQTT topic structure to publish to, (b) what payload format AgCloud expects, (c) what the existing leaf-pipeline does and whether it should be extended.
- `pyiqa` README and metric list — `https://github.com/chaofengc/IQA-PyTorch`. Skim FR vs NR; install and run BRISQUE/NIQE on a few webcam frames. The IQA framing for this project is **camera-flaw detection**: how blurry, how dark, how out-of-focus is this frame? Not absolute aesthetic quality.
- Sims & Johnson, *Scrum: A Breathtakingly Brief and Agile Introduction* (Agile Learning Labs) — `https://agilelearninglabs.com/resources/scrum-introduction/`. The whole-team Scrum mechanics primer, ~40 pages, intentionally short. Covers roles, sprint cycle, backlog, ceremonies, and Definition of Done in the time it takes to read a long blog post. If anyone on the team hasn't worked in Scrum before, this is the baseline. The companion "Scrum in 13 Minutes" video on the same page works too if students prefer.

**Stretch reading**
- Project AgML — `https://github.com/Project-AgML/AgML` — academic Python library aggregating ag datasets and pretrained models behind a consistent API.
- Schwaber & Sutherland, *The Scrum Guide* — `https://scrumguides.org/scrum-guide.html`. The official ~13-page canonical reference, updated 2020. More authoritative and more terse than Sims & Johnson; a useful follow-up if a question arises mid-sprint about what Scrum "officially" says about something. Worth bookmarking even if not read cover-to-cover.

**Pre-work for the AgCloud Q&A session**
Before scheduling any time with the AgCloud-experienced team member or the previous cohort, the team should have:
- Read the AgCloud README and skimmed the four directories above.
- Drafted a concrete questions list. Examples worth bringing: *Which MQTT topics are reserved for which device types? What's the message envelope (CBOR? JSON? Protobuf)? How does the leaf-pipeline currently consume images — pulled from MinIO or pushed via Kafka? Are there breaking changes between the version we're reading and what was deployed last cohort? Is `docker compose up` actually enough, or are there hidden setup steps?*
- A draft of the orientation memo (below) ready to validate during the session.

This makes one Q&A hour worth ten of asking-as-you-go.

**Sprint commits (must deliver)**
- **AgCloud orientation memo** (1–2 pages, owned by a designated team member). DoD: documents the MQTT topic + payload contract that vision will produce, summarizes the existing leaf-pipeline, lists which AgCloud components vision will integrate with vs. work around. Validated against AgCloud Q&A. Reviewed and signed-off by the cloud team.
- **Interface contract document**: explicit specs for every pipeline boundary — `(image_source) → (iqa_gate) → (detector) → (json_serializer) → (mqtt_publisher) → (cloud_sink)`. DoD: each boundary documents input type, output type, error semantics, and threading/async assumptions. Reviewed by another team member.
- **`frame_quality.py` CLI**: produces BRISQUE, NIQE, Laplacian-variance, and mean-luminance scores per image. DoD: runs on a directory of images, outputs CSV, has documented thresholds tuned for camera-flaw detection (not aesthetic ranking). Tested on at least 20 webcam frames including some deliberately bad ones.
- **Existing-models survey** (one page). DoD: at least 8 pretrained ag detection / classification candidates listed with task, dataset trained on, **license**, framework, and last-updated date. Sources canvassed: Roboflow Universe, Project AgML, HuggingFace, Ultralytics Hub, GitHub.
- **Licensing decision** (one page). DoD: explicit team decision, with rationale, on Ultralytics AGPL vs. permissive-licensed alternatives (RF-DETR Apache 2.0, YOLOX Apache 2.0, YOLO-NAS Apache 2.0, MMDetection Apache 2.0). Reviewed by the OJT lead. This decision gates Sprint 2's stub framework choice.
- **Curated datasets list**. DoD: starting from the organizer's previous-year sheet, supplemented with 2024–2026 sources, with leakage/contamination notes per dataset.
- **Working training environment**. DoD: PyTorch + chosen framework installed, CVAT (self-hosted via Docker) and/or Roboflow account ready, LaboroTomato + IP102/AgriPest + PlantDoc downloaded and inventoried, unified eval-harness skeleton (mAP@0.5, mAP@0.5:0.95, per-class breakdown, latency).
- **Data ontology decision** (one page). DoD: documents what counts as a fruit class, ripeness state, pest class, disease class, soil-quality class; class-naming convention; split policy.

**Backlog items (deliver if time, prioritized top-down)**
- Local Docker Compose setup for AgCloud — running the platform locally, not just reading the code, accelerates Sprint 2.
- Trial run of pyiqa on real webcam captures with deliberately-induced flaws (defocus, motion blur, underexposure) to validate threshold choices.
- Set up CI for the frame_quality CLI.

**Standalone lab for next cohort: "Existing-Work Audit"**
Given an active open-source agriculture platform and a team's own modeling task, produce in one week (a) an integration contract memo with the platform team, (b) a curated list of pretrained ag models relevant to the task with explicit license check, and (c) a curated dataset list with notes on contamination/leakage risks.

**Cross-team checkpoints**
- *Cloud team (Kayvan):* Confirm the MQTT topic + payload contract from the AgCloud orientation memo. The cloud team is also working on AgCloud, so the conversation is "are we both pointing at the same MQTT topics with the same schema." Get this nailed in Week 1.
- *Embedded team (Pavan):* Get the **decision on Pi model + accelerator** by end of Week 2. Coral USB Accelerator is effectively dead in 2026 (driver support gone, stock zero); the realistic accelerator path is the **Raspberry Pi AI HAT+** (Hailo-8L 13 TOPS or Hailo-8 26 TOPS). Otherwise, CPU-only Pi 5 with NCNN/ONNX is the default. This decision drives Sprint 3's edge work.
- *Data Team A (Ingyu):* Confirm IMU data will be timestamped and accessible alongside frames.
- *Organizer:* Schedule the previous-cohort Q&A for Week 2, after the team has read AgCloud's repo and has sharper second-round questions.

**Retro prompts**
- Did the team underestimate AgCloud's complexity? By how much, and what should the next phase's planning account for?
- Was the licensing decision easy to converge on, or contentious? If contentious, what does that say about how Sprint 2's framework choice should be socialized?
- Did the AgCloud Q&A session land? Or were the questions unfocused / answers vague?

---

## Sprint 2 — End-to-End Skeleton with Stubs
**Weeks 3–4 (Phase 2)**

**Sprint goal:** A demoable pipeline runs end-to-end by end of Week 4 with maximally simple components — synthetic input, stub detector, real IQA gate, real MQTT, real cloud sink. The pipeline's *shape* is the deliverable, not its accuracy.

This is *not* the "first detector" sprint — it's the "first running system" sprint. Students will discover that the hard parts of edge ML aren't the models — they're frame timing, JSON serialization quirks, MQTT topic naming, error semantics when the camera disconnects, what happens when the IQA gate rejects every frame. Surfacing these in Week 4 is far cheaper than surfacing them in Week 9.

In parallel, the fruit pretrained-model evaluation runs as an independent thread on developer laptops. By end of Sprint 2, the team has both (a) a working stub pipeline and (b) a chosen real fruit detector ready to swap in next sprint.

**Data progression target**: synthetic/fake fixtures → test webcam captures → live webcam by end of sprint.

**Required reading**
- AgCloud `simulators/` source code — read it to understand how previous cohorts stubbed device data into the platform. The team's stub strategy should mirror their patterns.
- Eclipse Mosquitto quickstart docs — `https://mosquitto.org/documentation/`. Local broker setup is a 10-minute task; running one alongside development saves hours of "is AgCloud's broker up" debugging.

**Stretch reading**
- Martin Fowler, *"Mocks Aren't Stubs"* — `https://martinfowler.com/articles/mocksArentStubs.html`. The vocabulary helps the team be precise about what each stub is doing and how it'll be replaced.

**Sprint commits (must deliver)**
- **End-to-end skeleton running** with synthetic input → stub detector → real IQA gate → JSON serialization → MQTT publish → cloud sink (local broker, or AgCloud if available). DoD: demo to PO/lead, messages observable on cloud sink, runs for at least 5 minutes without crashing.
- **Stub detector**: explicitly simple, version-controlled, swappable behind the Sprint 1 interface contract. DoD: returns 0–3 fake bboxes per frame with a configurable always-tomato class; documented limitations on a pipeline-status README so no one mistakes its output for real detections later.
- **Synthetic input source**: generates frames programmatically (random noise, simple geometric scenes, sampled public images). DoD: wrapped behind the Sprint 1 interface, swappable with webcam source.
- **Webcam input source**: real `cv2.VideoCapture` implementation behind the same interface. DoD: drop-in replacement for synthetic source, demonstrated swap with pipeline still running.
- **Test harness**: end-to-end tests that prove messages flow through. DoD: includes failure-injection cases (camera disconnect, IQA gate rejects all frames, MQTT broker unreachable). At least 5 tests that pass.
- **Pretrained-model evaluation matrix** for fruit detection. DoD: 3–5 candidate pretrained tomato/fruit detectors evaluated on LaboroTomato's test split using the unified eval harness. mAP@0.5, mAP@0.5:0.95, per-class AP, and CPU inference latency reported per candidate. Recommendation memo for which model to swap in next sprint, with rationale.

  > **Results — Pretrained-model evaluation matrix (Sprint 2, completed)**
  >
  > #### Detection model — LaboroTomato test set (161 images)
  >
  > | Model | Dataset | Scoring | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | Latency (ms/img, CPU) |
  > |---|---|---|---|---|---|---|---|
  > | yolov8-fruits.pt (AgCloud COCO) | LaboroTomato/test | class-agnostic¹ | **0.471** | 0.344 | 0.871 | 0.264 | ~283 |
  >
  > ¹ "tomato" is not in the COCO 80-class label set. GT boxes and predictions are collapsed to a single "object" class. Measures localisation only — the model fires "apple"/"orange" for tomatoes.
  >
  > #### Ripeness classifier — zero-shot transfer (best_conditional.pt, 1996 GT crops)
  >
  > | Fruit surrogate | Accuracy | Mean confidence |
  > |---|---|---|
  > | apple (best) | **63.0%** | 0.941 |
  > | pineapple | 62.9% | 0.941 |
  > | orange | 62.9% | 0.940 |
  > | banana | 62.7% | 0.940 |
  >
  > GT mapping: `b/l_green`→unripe · `b/l_half_ripened`→ripe · `b/l_fully_ripened`→ripe. Fruit surrogate choice has <0.3% spread — the MobileNetV3 backbone drives accuracy, not the fruit embedding.
  >
  > **Recommendation:** Both models show transfer to tomatoes without any fine-tuning. The detector localises tomato regions (mAP@0.5=0.47) but mislabels them as apple/orange; the ripeness classifier achieves 63% zero-shot accuracy (well above the 50% binary random baseline). Recommended Sprint 3 action: fine-tune `yolov8-fruits.pt` on LaboroTomato train split (643 images, already on disk) to add a tomato class; add tomato training examples to the ripeness model (architecture unchanged — only the embedding needs new data). Raw metrics and demo images: `eval_out/`.

**Backlog items (deliver if time, prioritized top-down)**
- **Pipeline observability stub**: minimal logging/metrics so the team can see what's happening end-to-end. Doesn't need to be Grafana-grade yet, but the hooks should be there.
- Light fine-tune of the chosen fruit candidate on LaboroTomato (a few epochs at low LR with `albumentations`) — accelerates Sprint 3 if it lands here.
- Containerize the pipeline (Dockerfile) — useful for Pi deployment in Sprint 3.
- AgCloud-broker integration — if local mosquitto is fine, defer; if AgCloud broker is available and stable, prefer it.

**Standalone lab for next cohort: "Stub Skeleton"**
Build a multi-stage data pipeline end-to-end with a stub at every component, then progressively replace stubs with real implementations. Demonstrate on a Raspberry Pi or laptop a working pipeline before any real ML model is loaded.

**Cross-team checkpoints**
- *Cloud team:* **First end-to-end "vision → AgCloud" smoke test should happen this sprint**, even if only with synthetic frames and stub detections. This is the integration milestone — getting it working in Sprint 2 means everything from Sprint 3 onward is replacing components, not debugging integration.
- *Embedded team:* Confirm Sprint 1's accelerator decision hasn't changed. If they have any early hexapod camera footage (even an iPhone held over a plant), the team can use it as test-cam data immediately.
- *Data Team A:* Soft check-in — share the pipeline interface contracts. They may want to know how detections are timestamped, since they'll eventually want to correlate detections with leg-pose state.

**Retro prompts**
- Was the discipline of *not* using a real model painful? Did anyone try to slip one in?
- Did the interface contracts from Sprint 1 hold up, or did they need revision the moment the team started implementing?
- Did the team-internal demo at end of Sprint 2 actually look demoable, or was it held together with debug print statements?

---

## Sprint 3 — Real Fruit Detector + Edge Deployment
**Weeks 5–6 (Phase 3)**

**Sprint goal:** Real fruit detector running end-to-end on a Raspberry Pi by end of Week 6, integrated into the pipeline from Sprint 2 and publishing to AgCloud.

This is the project's most consequential sprint. Two distinct hard things converge: replacing the Sprint 2 stub with a real fruit model, and deploying to the Pi with quantization and benchmarking. Pulling edge deployment forward (originally Phase 4) de-risks the project's primary KPI — if something about the chosen Pi or accelerator surprises the team, it's surfaced now with two sprints left to recover.

The sprint is **internally sequenced** with an **end-of-Week-5 mid-sprint checkpoint** to prevent the team from getting stuck in a debugging fog where it's unclear whether problems are in the model, the export, the runtime, or the hardware:

- **Week 5: model in pipeline, on laptop.** The chosen fruit detector replaces the stub; pipeline runs end-to-end on a developer laptop with webcam input. By Friday of Week 5, the team should be able to demo the laptop-resident pipeline. **If this isn't working by EOW Friday Week 5, the PO and team should renegotiate Week 6 scope** — see fallback below.
- **Week 6: port to Pi.** Take the working laptop pipeline and port it. Export, quantize, benchmark, deploy.

This isn't a separate phase, just an explicit internal cadence within the sprint. It maps to a sprint mid-point review, which is a reasonable Scrum practice for high-risk sprints.

**Data progression target**: live webcam captures becoming the team's primary working data; first ingest of test robo data (recorded hexapod footage) if available.

**Required reading**
- LaboroTomato repo + dataset card — `https://github.com/laboroai/LaboroTomato`. Inspect the size×ripeness label structure before evaluating any model.
- Ultralytics *Quick Start Guide: Raspberry Pi* — `https://docs.ultralytics.com/guides/raspberry-pi/`, **OR** the equivalent docs for whichever model framework the team chose in Sprint 1's licensing decision (RF-DETR's deployment docs, MMDeploy, etc.). The benchmark table at the bottom is the team's anchor expectation.

**Stretch reading**
- The `hailo-ai/hailo-rpi5-examples` repo — `https://github.com/hailo-ai/hailo-rpi5-examples`. A YOLO + tracker pipeline running at 30 FPS on a Pi 5 is genuinely impressive. Required if AI HAT+ is in the BOM.

**Sprint commits (must deliver — Week 5 portion)**
- **Fruit detector swapped into the pipeline on laptop**: Sprint 2's stub replaced with the chosen real model. DoD: pipeline runs end-to-end, MQTT messages observed on cloud sink, demo-ready by EOW Friday Week 5.
- **Light fine-tune of fruit detector on LaboroTomato** (if not already done in Sprint 2 backlog). DoD: a few epochs at low LR with `albumentations` bbox-safe augmentation. Compare to zero-shot result; document if fine-tuning didn't help.
- **Failure-mode writeup for the fruit detector**. DoD: documents which size/ripeness combinations confuse the model, where occlusion hurts, where lighting hurts. Includes example failure-case images.

**Sprint commits (must deliver — Week 6 portion)**
- **Multi-format export**: the chosen fruit model exported to at least one of NCNN, ONNX Runtime, TFLite, Hailo HEF (if AI HAT+). DoD: model loads and runs on the Pi, produces matching outputs to FP32 reference within tolerance.
- **Live pipeline on the Pi**: `Camera → IQAGate → FruitDetector → JSON → MQTT-to-AgCloud`, running on real hardware. DoD: end-to-end latency measured (camera read → preprocess → inference → postprocess → JSON serialize → MQTT publish, not just network forward time), runs for at least 5 minutes without crashing.
- **Post-training INT8 quantization** of the chosen fruit model with calibration on a held-out subset. DoD: mAP delta documented vs. FP32 reference; recommendation on whether to ship INT8 or fall back to FP16/FP32.
- **Deployment recipe doc**. DoD: exact commands, dependencies, gotchas, with the team's quantization-calibration script versioned and reproducible. Another team member should be able to follow it from a fresh Pi.

**Backlog items (deliver if time, prioritized top-down)**
- **Second export format**, for benchmarking comparison. (Skipped from sprint commits to reduce Week 6 risk; if Week 5 went smoothly, this lands easily.)
- **Quantization-aware training (QAT)** on the fruit model. (Originally a sprint commit; demoted to backlog so Week 6 stays feasible.)
- **Test robo data ingest**: if hexapod footage exists by Week 6, run it through the live pipeline and report what happens.
- **Tracker integration** (e.g., ByteTrack) for visual demo polish.

**Fallback if Week 5 spills past Friday**
The PO and team renegotiate Week 6 scope. The minimum viable Week 6 is "model running on Pi in any export format, end-to-end pipeline working, end-to-end latency measured." The dropped scope (multi-format export, INT8 quantization, deployment recipe maturity) becomes Sprint 4 backlog. This is a 30% scope cut on the sprint, not a sprint slip — Sprint 4 absorbs the dropped breadth.

**Standalone lab for next cohort: "Skeleton-to-Pi"**
Take a working stub-pipeline from a previous lab and replace its stub detector with a real model, deploy to a Raspberry Pi, benchmark across export formats, and report end-to-end latency. End with a recommendation memo for which export to ship.

**Cross-team checkpoints**
- *Embedded team:* **Hard dependency** — the team needs a working Pi (with chosen accelerator) by Week 5. If it slips, fall back to a personal/office Pi. Confirm camera type (USB webcam, Pi Camera Module, Arducam) — capture code differs.
- *Cloud team:* They should be receiving live detections from the Pi by end of Week 6, with real payload size and cadence. Lets them validate Kafka/Flink throughput against real load before demo prep.
- *Data Team A:* If their stabilization or gait-control inference also runs on the Pi, both teams' latency budgets must add up to a sensible per-frame total.

**Retro prompts**
- Did the end-of-Week-5 checkpoint help? Did the team actually use it as a real decision point, or did they paper over problems and push through?
- If the fallback fired, why? Was it an integration issue, a model issue, or an accelerator/hardware issue?
- What did the team learn about end-to-end latency that they didn't expect?

---

## Sprint 4 — Pest Detection, Pipeline Hardening, and Soil
**Weeks 7–8 (Phase 4)**

**Sprint goal:** Add the project's hardest model (pest), commit a new task (soil), and harden the pipeline against real-camera conditions — all with the integration already proven in Sprint 3.

Pest detection on IP102/AgriPest is genuinely hard — long-tail, tiny-object, occluded, label-noisy. The team is no longer fighting integration at the same time, so they can focus on what makes pest detection difficult. Soil quality is a committed deliverable: image-based classifier for mold/discoloration/debris, integrated into the same pipeline. It earns its place by demonstrating the system extends to a non-detection task.

The "hardening" thread runs in parallel: the pipeline that worked on a developer's webcam in Sprint 3 needs to handle real camera quirks (motion blur, varied lighting, frame drops, MQTT disconnects). This is the sprint where IQA gate thresholds get tuned against real conditions, where reconnect logic matures, where the team adds whatever observability the demo will need.

**Data progression target**: test robo data running through the live pipeline; first live robo data if available.

**Required reading**
- *Crop Pest Classification Using Deep Learning Techniques: A Review* — arXiv:2507.01494 (2025). Skim sections on long-tail and tiny-object detection.
- Albumentations bbox-safe augmentation docs — `https://albumentations.ai/docs/3-basic-usage/bounding-boxes-augmentations/`. Important for tiny-object regimes; mosaic and copy-paste matter for IP102/AgriPest.

**Stretch reading**
- *AgriPest: A Large-Scale Domain-Specific Benchmark Dataset for Practical Agricultural Pest Detection in the Wild* (Wang et al., 2021).

**Sprint commits (must deliver)**
- **Pest detector**: pretrained model evaluated and (lightly) fine-tuned on a sensibly-chosen IP102 or AgriPest subset (8–15 economically-relevant classes for greenhouses, documented). DoD: model trains, mAP reported per class, fine-tune compared to zero-shot baseline.
- **Long-tail and tiny-object analysis**: per-class AP plotted against class frequency; AP broken down by COCO size buckets. DoD: one-page memo on the curve shapes and which mitigations the team tried (oversampling, focal loss, scale-jitter aug, mosaic). **Hard-timebox mitigations to ≤ 3 days** — research rabbit hole.
- **Pest detector deployed and quantized**: exported and benchmarked on Pi using the Sprint 3 pipeline. DoD: INT8 mAP delta documented; comparison with the fruit model's degradation is a finding worth writing up.
- **Soil quality classifier**: lightweight image-classification model (3–5 classes, e.g., healthy / mold / debris / dry / wet) trained on a public Kaggle soil image dataset. DoD: model trained, exported, integrated into the live pipeline as a parallel task, runs on Pi.
- **Pipeline hardening pass**. DoD: documented improvements to (a) IQA-gate thresholds tuned against real-condition footage, (b) MQTT reconnect/backpressure handling, (c) detector failure recovery, (d) frame-drop accounting and reporting. One-page change-log defending the decisions.

**Backlog items (deliver if time, prioritized top-down)**
- **Sprint 3 carry-overs if any** — multi-format export, QAT, etc.
- **Test/live robo data ingest**: if any real spider/hexapod data exists by Week 8, it should be running through the live pipeline.
- **QAT on pest model** for comparison with PTQ.
- **Pest detector tracker integration** (ByteTrack or similar) — useful for demo if there's pest video.
- **Grafana dashboard prototype** for the demo (saves Sprint 5 time).

**Standalone lab for next cohort: "Hard Model in a Soft Pipeline"**
Add a long-tail detection task to an existing edge-deployed pipeline, including export, quantization, hardening for real camera conditions, and integration of a parallel auxiliary task. End with a memo on which mitigations actually helped and which didn't.

**Cross-team checkpoints**
- *Cloud team:* Now receiving fruit, pest, and soil outputs through the live pipeline. Coordinate dashboard layout for the demo (Grafana panel design) — this becomes Sprint 5 work but conversations start here.
- *Embedded team:* Active push for spider/hexapod data — even shaky, badly-lit footage is high-value. The pipeline is ready to receive it.
- *Data Team A:* If their localization is producing any output, agree on how to tag detections with spatial info (frame-level robot pose) so the SLAM stretch in Sprint 5 is coherent.

**Retro prompts**
- Did pest detection bleed time into soil and hardening, or did the team manage the timebox?
- Was the integration of a new task type (classification rather than detection) easier or harder than expected? What does that say about the interface contracts?
- What real-condition issues surfaced during hardening that no one anticipated in Sprint 1's interface design?

---

## Sprint 5 — Disease, Lab-to-Field Cross-Eval, Real-Data Validation, and Demo
**Weeks 9–10 (Phase 5)**

**Sprint goal:** Land the project's central educational artifact (the lab-to-field cross-eval matrix), apply it to real spider/hexapod data if available, and ship a polished end-to-end demo.

Disease detection lands here because it's the moderate-difficulty task and pairs naturally with the lab-to-field cross-eval methodology (PlantVillage trained → PlantDoc/FieldPlant evaluated, and vice versa). **The cross-eval gap is the headline chart of the demo.** If real spider/hexapod data has been arriving (per Sprint 3+'s pipeline), the same cross-eval methodology gets applied to fruit, pest, and disease models against it — that real-data measurement is the most valuable single result the project will produce. Last 3–4 days reserved for documentation, demo prep, and writing the standalone-lab specs.

**Data progression target**: live robo data through the demo pipeline. If unavailable, recorded robo data; failing that, live cam data. The pipeline runs regardless.

**Required reading**
- Xu, Park, Lee, Yang, Yoon (2024), *Plant disease recognition datasets in the age of deep learning: challenges and opportunities*, Frontiers in Plant Science — `https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2024.1452551/full`. Read the dataset-bias and lab-vs-field sections carefully.
- FieldPlant Roboflow page + Moupojou et al. (2023) IEEE Access paper — for the second dataset to evaluate on. (PlantWild also fine if students prefer a more modern target.)
- Derby & Larsen, *Agile Retrospectives* — Chapter 1 ("Helping Your Team Inspect and Adapt") and the structure overview from Chapter 2. The full book is the canonical retrospectives reference, but for the project-level retrospective at end of Sprint 5, Chapter 1 plus the five-stage structure (Set the Stage → Gather Data → Generate Insights → Decide What to Do → Close) is enough to run a useful 90-minute retro. The team's retro at end of Sprint 5 should be an actual structured retrospective, not a casual debrief — it's one of the project's deliverables to the next cohort.

**Stretch reading**
- ORB-SLAM3 paper (Campos et al., IEEE TRO 2021; arXiv:2007.11898) **or** Swarm-SLAM (Lajoie & Beltrame, RA-L 2024; arXiv:2301.06230). Pointers for the collaborative-mapping stretch.
- Singer, *Shape Up: Stop Running in Circles and Ship Work that Matters* — `https://basecamp.com/shapeup` (free online, ~130 pages, ~2 hours). Basecamp's published methodology, deliberately positioned as a critique of and alternative to Scrum: 6-week cycles instead of 2-week sprints, no backlog, no daily standups, no velocity, and "circuit breakers" that cut unfinished work rather than carrying it over. The argument is that Scrum's standard cadences solve the wrong problems — that 2-week sprints encourage micro-optimization at the expense of meaningful shipped work, and that backlogs become "cemeteries of ideas" rather than priorities. Worth reading not because Robo-Greeno should adopt Shape Up, but because it sharpens the team's understanding of *which* parts of Scrum are mechanical conventions vs. which are doing actual work. After 10 weeks of practicing Scrum, students are positioned to read this critically rather than as either gospel or rejection. For broader context on the methodology landscape, the ObjectStyle comparison (`https://www.objectstyle.com/blog/agile-scrum-kanban-lean-xp-comparison`) covers Scrum vs. Kanban vs. Lean vs. XP at a higher level.

**Sprint commits (must deliver)**
- **Disease detector trained on PlantVillage and separately on PlantDoc or FieldPlant.** This is one of the few places in the project where training-from-scratch (or full fine-tuning) is the right call — the lab-to-field gap *is* the deliverable. DoD: both models trained, both evaluated on their own splits.
- **Cross-evaluation matrix (the headline result)**: PlantVillage-trained model evaluated on PlantDoc/FieldPlant, and vice versa. DoD: matrix populated, drop documented with example failure-case images, one-page interpretation memo.
- **End-to-end demo**: live pipeline running on Pi → MQTT → AgCloud → Grafana visualization of detections. DoD: demoable to stakeholders, runs for at least 10 minutes without intervention, all four model types (fruit, pest, soil, disease) visible.
- **Final writeup + standalone lab specs**. DoD: each phase's reusable lab written cleanly so the next cohort can run them. Final project writeup at least covers methodology, results, lab-to-field finding, and recommendations for next cohort.

**Backlog items (deliver if time, prioritized top-down)**
- **Real-data cross-eval (highest-value backlog item)**: for each of fruit, pest, and disease models, evaluate against real spider/hexapod imagery if any has been collected. Report mAP delta vs. each model's public-dataset performance. **Prioritize this above all other backlog items.**
- **SLAM proof-of-concept**: ORB-SLAM3 on a hand-moved webcam producing a rough trajectory, OR Swarm-SLAM offline two-trajectory merge in sim. Pick one, one day.
- **Demo polish**: dashboard styling, recorded video of the system running, etc.

**Fallback if Sprint 4 spilled or integration regression hits**
Reduce the disease deliverable from "train two models and cross-evaluate" to "train one disease model on PlantDoc/FieldPlant only, and apply the cross-eval methodology to existing fruit and pest models against any available out-of-distribution data." The lab-to-field narrative and headline chart survive, just with different model pairings.

**Standalone labs for next cohort**
- *"Mind the Gap":* Train a model on PlantVillage, evaluate on PlantDoc, write a memo explaining the accuracy drop and what realistic mitigations exist.
- *"Webcam-to-AgCloud":* Build an end-to-end pipeline from camera capture through quality gating, detection, and MQTT publish to a running AgCloud instance, on a Raspberry Pi.

**Cross-team checkpoints**
- *Embedded team:* If the hexapod is producing real camera data by Week 9, that's the most valuable single asset for the demo. A single hour of real footage outperforms a week of public-dataset work.
- *Cloud team:* AgCloud integration was validated back in Sprint 2 and matured through Sprints 3–4. This sprint is dashboard polish; coordinate Grafana layout.
- *Data Team A:* If they have any localization output, even rough, tag detections spatially in the JSON. Makes the SLAM stretch coherent.

**Retro prompts (project-level retro at end of Sprint 5)**
- Did the end-to-end-first methodology pay off? Where would the project be if it had been built phase-by-component instead?
- Did the stub-then-swap discipline hold up across all five sprints?
- Which cross-team checkpoint was most painful, and what would the team change about how it was handled?
- What's the single piece of advice this team would give the next cohort?

---

## Sidetrack: Camera Calibration (as-needed, not sprint-bound)

Postponed from Sprint 1 per organizer's instruction. Re-enters as a one-day spike whenever real cameras come online and the team needs intrinsics for a specific downstream task — most likely:
- Stereo or depth from the spider's stereo pair
- Hand-eye calibration once a manipulator end-effector exists
- Undistortion for a wide-FOV lens if one is chosen

Reference materials when needed: OpenCV Python tutorial (`https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html`) and the LearnOpenCV calibration guide. Use a ChArUco board, capture 20–40 varied poses, always check per-image reprojection error.

**Standalone lab name (for whenever it does happen): "Calibrate-a-Cam".**

---

## Cross-cutting concerns to track from Week 1

- **End-to-end-first is the project's core methodology.** Every sprint moves the system toward "more real" while never breaking the working pipeline. If a sprint ends with the pipeline broken, something went seriously wrong.
- **Stub-then-swap requires honest interfaces.** The Sprint 1 interface contract document is the lever that makes the rest of the project work. A vague interface produces stubs that don't drop-in-replace, which produces Sprint 5 panic.
- **Data progression** — fake → test cam → live cam → test robo → live robo. The team is never blocked waiting; they always have viable input to the left of where they want to be, and they're always ready to swap in real data when it arrives.
- **AgCloud is the integration target, not a future "we'll figure it out" problem.** Sprint 2 is when integration is working end-to-end with synthetic data. The AgCloud-experienced team member is a *consultable resource*, not a contributor.
- **Existing models first.** Fight the urge to train from scratch when a reasonable pretrained model exists. The exception is Sprint 5's disease cross-eval, where two distinct training distributions are part of the deliverable.
- **License decision (Ultralytics AGPL vs. permissive alternatives)** is locked in Sprint 1 and affects every subsequent model choice.
- **PlantVillage is contaminated.** Drill this in early; it shows up everywhere students will Google.
- **Coral USB Accelerator is dead in 2026.** If anyone proposes it (organizer included), redirect to AI HAT+ (Hailo) or CPU-only Pi 5.
- **AlbumentationsX has an AGPL trap.** Pin to MIT-licensed `albumentations` if there's any chance of permissive-license release.
- **Bbox-safe cropping** and **per-image evaluation breakdowns** — silent failure modes that bite every cohort.
- **Annotation budget.** When real robot images arrive, the team will need to label some for evaluation. Have CVAT ready; don't underestimate hours.
- **The lab-to-field gap is the project's central narrative.** Sprint 5 measures it. If only one chart appears in the final demo, it's this one.
- **Network optimization for embedded is the project's primary KPI per the organizer**, landing in Sprint 3 (pulled forward from Sprint 4) for de-risking.
