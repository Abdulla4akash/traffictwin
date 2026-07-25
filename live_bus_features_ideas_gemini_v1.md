# Live Bus Features & Research Ideas — TrafficTwin Integration (v1)

## Executive Summary
This document outlines comprehensive research proposals and technical architectures for integrating **Manchester Live / Historical Bus Data** into **TrafficTwin**. 

These proposals directly build upon the findings in **Randy Prasetia Putra's Year 1 PhD Report** (*Intelligent Task Offloading: Current State Limitations and Proposed Potential Solutions*), which highlighted how state-of-the-art Deep Reinforcement Learning (DRL) algorithms deteriorate under non-stationary real-world traffic data and suffer from severe local-offloading reward misalignment (~94.3% local bias).

---

## Part 1: Core Research Proposals

### 1. Buses as "Mobile RSUs" (Moving Edge Servers)
* **Concept**: Fixed Roadside Units (RSUs) are expensive to deploy across entire urban road networks. Public transit buses follow fixed, predictable routes, carry high-capacity electrical systems, and can house mobile GPU/CPU edge compute servers.
* **TrafficTwin Implementation**:
  * Ingest live GTFS-RT / Manchester bus GPS streams to model dynamic `MobileRSU` coordinates over time.
  * Dynamically calculate coverage radii ($R_{\text{V2I\_bus}} = 250\text{m}$) around moving buses.
* **What-If Experiment**: *"If 20% of Stagecoach / First buses along Oxford Road carry mobile edge servers, how much does offloading latency drop for surrounding passenger vehicles during peak hours?"*

### 2. UK Urban Traffic Calibration (Manchester vs. Berlin)
* **Concept**: Existing baseline models use synthetic highway data (e.g. Berlin A100 motorway). UK urban corridors feature unique dynamics: narrow lanes, dedicated bus lanes, frequent stops, and high pedestrian density.
* **TrafficTwin Implementation**:
  * Build a `ManchesterBusAdapter` in `src/traffictwin/ingestion/` that parses Manchester Open Data feeds into SUMO route files (`.rou.xml`).
* **What-If Experiment**: Benchmark DRL offloading policies trained on highway data against real Manchester urban congestion to measure policy degradation.

### 3. Task-Specific Priority Offloading (`task0`, `task1`, `task2`)
* **Concept**: Offloading policy performance must be evaluated separately across task profiles:
  * **`task0` (Safety)**: Deadline 0.06s (60ms), 400KB data, 60M CPU cycles.
  * **`task1` (Autonomous Driving)**: Deadline 0.10s (100ms), 900KB data, 200M CPU cycles.
  * **`task2` (Infotainment)**: Deadline 0.80s (800ms), 4.0MB data, 1.2B CPU cycles.
* **TrafficTwin Implementation**:
  * Track deadline failure rates and latency breakdown per task type when offloading to bus nodes vs. static RSUs vs. local execution.

### 4. Deterministic Historical Replay vs. Live What-If
* **Concept**: Live data changes daily, making reproducible scientific evaluation difficult.
* **TrafficTwin Implementation**:
  * Freeze 2-hour windows of recorded Manchester bus stream data (e.g., Friday 17:00–19:00 rush hour) into deterministic `EvidencePack` bundles.
  * Run **Student-t TOST paired equivalence testing** and **N-way Policy Ranking** over these frozen real-world historical traces.

### 5. Weather & Event Anomaly Stress-Testing
* **Concept**: Weather (rain) and major events (Manchester United / City matchdays, Parklife festival) cause sudden non-linear traffic delays.
* **TrafficTwin Implementation**:
  * Compare `EvidencePack` metrics from rainy vs. sunny days in Manchester.
* **What-If Experiment**: Test if DRL offloading agents recover or experience catastrophic task deadline failure when weather anomalies occur.

### 6. Multi-Modal Transit Edge (Buses + Metrolink Trams)
* **Concept**: Manchester features both a bus network and the **Metrolink Tram** system. Trams operate on dedicated tracks with zero traffic jam delays and continuous high power.
* **TrafficTwin Implementation**:
  * Model **Metrolink Trams** as zero-latency-jitter mobile edge anchors and compare performance against traffic-bound bus nodes.

### 7. 5G Signal Shadowing (Double-Decker Bus Obstruction)
* **Concept**: Double-decker buses physically block 5G millimeter-wave (mmWave) Line-of-Sight (LoS) signals between private passenger cars and fixed RSUs.
* **TrafficTwin Implementation**:
  * Add a line-of-sight raytracing check: when a double-decker bus is positioned between a vehicle and an RSU, apply a signal attenuation penalty (+15–30ms latency).

### 8. Emergency Vehicle Corridor Clearing
* **Concept**: Emergency vehicles (ambulances/fire engines) travelling down corridors like Oxford Road require instant, ultra-low latency V2X communication.
* **TrafficTwin Implementation**:
  * Implement an emergency preemptive policy: when an ambulance approaches, bus edge nodes immediately drop/flush low-priority `task2` (Infotainment) workloads to guarantee 100% CPU availability for `task0` safety tasks.

### 9. Micro-Incentive & Credit Economy Simulation
* **Concept**: Bus operators require financial or computational incentives to process third-party vehicular tasks.
* **TrafficTwin Implementation**:
  * Add a token-bidding module where private vehicles bid micro-credits for bus compute cycles, evaluating efficiency under economic constraints.

### 10. Interactive Manchester Digital Twin Dashboard (Streamlit UI)
* **Concept**: Elevate TrafficTwin's presentation layer for supervisor/viva demonstrations.
* **TrafficTwin Implementation**:
  * Build a PyDeck / Mapbox GIS map component inside Streamlit:
    * 🔴 **Red Nodes**: Overloaded static RSUs.
    * 🟢 **Green Nodes**: Manchester buses with available CPU capacity.
    * 🔵 **Blue Nodes**: Passenger cars requesting task offloading.
    * ⚠️ **Yellow Flashing Alerts**: `task0` deadline violations.

---

## Part 2: Architecture & Code Integration Plan

To implement these features into `TrafficTwin`, modify/add the following modules:

```text
src/traffictwin/
├── ingestion/
│   ├── manchester_bus_adapter.py     <-- [NEW] Parses GTFS-RT / Manchester Open Data
│   └── sumo_output_adapter.py
├── domain/
│   ├── mobile_rsu.py                 <-- [NEW] Models moving bus/tram compute nodes
│   └── task_profile.py               <-- Defines task0, task1, task2 SLAs
├── rules/
│   ├── bus_preemption_rules.yaml     <-- [NEW] Emergency & mobile offloading rules
│   └── default_rules.yaml
├── ui/
│   ├── components/
│   │   └── manchester_map_view.py    <-- [NEW] Streamlit GIS map visualization
│   └── app.py
```

---

*Generated by Antigravity (Gemini 3.6 Flash)*
