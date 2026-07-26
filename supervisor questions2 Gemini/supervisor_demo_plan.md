# Supervisor Demo Plan (TrafficTwin Guided Demo)

This document contains the step-by-step execution sequence and talking points for presenting the TrafficTwin v0.7 guided demo to your supervisor.

## 1. Launch the Demo UI
First, initialize and start the demo workspace:
```bash
cd /Users/akashx/AntigravityTest/diss
source .venv/bin/activate
traffictwin demo launch
```
*(When the UI opens, navigate to the **Guided workflow** in the sidebar and select the **Standalone synthetic** track.)*

## 2. Follow the Guided Steps (Standalone Track)

### Step 1: Frame a reproducible experiment (Experiment Planner)
*   **What to do:** Open the Experiment Planner. Validate the comparison design and build a bounded run-matrix preview.
*   **Action:** Click the button to register the experiment plan.
*   **Explain to Supervisor:** Show how you aren't just running simulations blindly; you are registering strict, versioned experimental designs first. The guide enforces this boundary.

### Step 2: Validate a run bundle (Bundle Import)
*   **What to do:** Select the synthetic baseline bundle. Let the tool validate its schemas, units, and evidence availability.
*   **Explain to Supervisor:** Point out the machine-readable validation findings. Emphasize that the tool forces strict data validation before any analysis can begin.

### Step 3: Inspect deterministic metrics (Run Overview)
*   **What to do:** Look at the generated task metrics.
*   **Explain to Supervisor:** Deliberately show her at least *one unavailable metric* along with its reason code. This proves that the tool is honest about its limitations and doesn't invent missing data.

### Step 4: Compare baseline and stress (Compare)
*   **What to do:** Check compatibility and calculate deterministic deltas between the baseline and a stressed run.
*   **Explain to Supervisor:** Point out the absolute and relative changes. State clearly that "a change is not automatically labelled better, worse, or causal"—you are just presenting deterministic, objective evidence.

### Step 5: Replay historical records (Operations)
*   **What to do:** Advance the logical clock and filter records to a selected time window.
*   **Explain to Supervisor:** Demonstrate how the map updates dynamically. Reiterate that this is a historical replay of fixed records, not a live stream interpolating missing data. 

### Step 6: Inspect candidate hypotheses (Evidence/Diagnostics)
*   **What to do:** Evaluate the deterministic rules (R0-R3) against the evidence pack.
*   **Explain to Supervisor:** Show the generated candidate hypotheses. Remind her that these are structured diagnostic leads based strictly on data, *not* proven root causes.

### Step 7: Trace a result to source evidence (Provenance)
*   **What to do:** Click on a metric or diagnostic result and trace its lineage back to the source rows.
*   **Explain to Supervisor:** Show the JSON or Markdown lineage. This is a huge selling point: it proves complete auditability for every data point and ensures no AI hallucination is injected into the science.

### Step 8: Export a research report (Reports)
*   **What to do:** Regenerate the deterministic Markdown or HTML report. 
*   **Action:** Hit the "regenerate" button to finish the guide.
*   **Explain to Supervisor:** Show that the final report includes all limitations, source context, and provenance automatically, making your research perfectly reproducible.
