import path from "node:path";
import { pathToFileURL } from "node:url";

import { Presentation, PresentationFile } from "@oai/artifact-tool";

const WIDTH = 1280;
const HEIGHT = 720;
const FONT = "Helvetica Neue";
const INK = "#050505";
const MUTED = "#5E6572";
const LIGHT = "#F2F4F6";
const LINE = "#D8DCE2";
const BLUE = "#2359FF";
const PALE_BLUE = "#DDE7FF";
const WHITE = "#FFFFFF";

function addText(slide, value, position, options = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  box.text = value;
  box.text.style = {
    typeface: FONT,
    fontSize: options.fontSize ?? 22,
    bold: options.bold ?? false,
    color: options.color ?? INK,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "top",
    autoFit: options.autoFit ?? "shrinkText",
    wrap: "square",
    insets: options.insets ?? { top: 0, right: 0, bottom: 0, left: 0 },
  };
  return box;
}

function addSurface(slide, position, options = {}) {
  return slide.shapes.add({
    geometry: options.geometry ?? "roundRect",
    position,
    fill: options.fill ?? LIGHT,
    line: {
      style: "solid",
      fill: options.line ?? "none",
      width: options.lineWidth ?? 0,
    },
    borderRadius: options.borderRadius ?? "rounded-xl",
  });
}

function addFooter(slide, number, message) {
  addText(
    slide,
    message,
    { left: 41, top: 668, width: 1030, height: 22 },
    { fontSize: 13, color: MUTED },
  );
  addText(
    slide,
    String(number).padStart(2, "0"),
    { left: 1185, top: 661, width: 54, height: 27 },
    { fontSize: 13, alignment: "right", color: MUTED, verticalAlignment: "bottom" },
  );
}

function addSlideTitle(slide, title, number) {
  addText(
    slide,
    title,
    { left: 41, top: 32, width: 1198, height: 66 },
    { fontSize: 48, bold: true, autoFit: "none" },
  );
  addText(
    slide,
    `TRAFFICTWIN · SUPERVISOR CHECKPOINT · ${String(number).padStart(2, "0")}`,
    { left: 42, top: 116, width: 700, height: 24 },
    { fontSize: 13, bold: true, color: BLUE },
  );
}

function setSources(slide, lines) {
  slide.speakerNotes.textFrame.setText(["[Sources]", ...lines]);
  slide.speakerNotes.setVisible(true);
}

function buildCover(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = WHITE;

  addText(
    slide,
    "SUPERVISOR CHECKPOINT · 2 AUGUST 2026",
    { left: 41, top: 41, width: 760, height: 44 },
    { fontSize: 22, bold: true, color: BLUE },
  );
  addText(
    slide,
    "TrafficTwin",
    { left: 41, top: 180, width: 1120, height: 235 },
    { fontSize: 82, bold: true, verticalAlignment: "bottom", autoFit: "none" },
  );
  addText(
    slide,
    "A verifiable what-if loop for traffic and edge-computing research",
    { left: 41, top: 493, width: 760, height: 116 },
    { fontSize: 31, color: INK },
  );
  addText(
    slide,
    "Communication artifact · not supervisor approval or scientific evidence",
    { left: 41, top: 656, width: 910, height: 23 },
    { fontSize: 13, color: MUTED },
  );

  setSources(slide, [
    "Project documentation: docs/current_progress_v0_7.md and docs/implementation-status.md (repository truth at Phase 180).",
    "Communication design: docs/presentations/supervisor_deck_and_bibliography_design.md.",
    "Literature context: Fuller et al., IEEE Access 2020, DOI 10.1109/ACCESS.2020.2998358; van der Valk et al., Computers in Industry 2022, DOI 10.1016/j.compind.2022.103716.",
    "Source class: project documentation plus literature context. No slide-specific project measurement is asserted here.",
  ]);
  return slide;
}

function buildLoop(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = WHITE;
  addSlideTitle(slide, "One loop, two lenses—no silent promotion", 2);

  addText(
    slide,
    "The differentiator is the binding between a question, its execution boundary, its measurements and its claim state.",
    { left: 41, top: 151, width: 1160, height: 50 },
    { fontSize: 22, color: MUTED },
  );

  const nodes = [
    { label: "OBSERVE", body: "Official feeds + supplied traces", left: 41 },
    { label: "CANONICAL TWIN", body: "Provenance, units + gaps", left: 342 },
    { label: "ASK “WHAT IF?”", body: "Bounded mutation + campaign", left: 643 },
    { label: "EVALUATE", body: "Metrics, receipts + claim state", left: 944 },
  ];
  const surfaces = nodes.map((node, index) =>
    addSurface(
      slide,
      { left: node.left, top: 215, width: 255, height: 126 },
      {
        fill: index === 2 ? BLUE : LIGHT,
        line: index === 2 ? BLUE : LINE,
        lineWidth: 1,
      },
    ),
  );

  for (let index = 0; index < surfaces.length - 1; index += 1) {
    slide.shapes.connect(surfaces[index], surfaces[index + 1], {
      kind: "straight",
      fromSide: "right",
      toSide: "left",
      line: { style: "solid", fill: BLUE, width: 2 },
      tail: { type: "triangle", width: "sm", length: "sm" },
    });
  }
  slide.shapes.connect(surfaces[3], surfaces[0], {
    kind: "elbow5",
    fromSide: "bottom",
    toSide: "bottom",
    line: { style: "dashed", fill: MUTED, width: 1.5 },
    tail: { type: "arrow", width: "sm", length: "sm" },
  });

  nodes.forEach((node, index) => {
    const textColor = index === 2 ? WHITE : INK;
    addText(
      slide,
      node.label,
      { left: node.left + 18, top: 235, width: 219, height: 32 },
      { fontSize: 22, bold: true, color: textColor },
    );
    addText(
      slide,
      node.body,
      { left: node.left + 18, top: 280, width: 219, height: 48 },
      { fontSize: 21.5, color: textColor },
    );
  });

  addText(
    slide,
    "Feedback preserves refutations and gaps for the next observation",
    { left: 315, top: 358, width: 650, height: 26 },
    { fontSize: 17, color: MUTED, alignment: "center" },
  );

  addSurface(slide, { left: 41, top: 413, width: 569, height: 119 }, { fill: LIGHT });
  addText(
    slide,
    "MOBILITY & TRAFFIC",
    { left: 62, top: 433, width: 530, height: 36 },
    { fontSize: 30, bold: true },
  );
  addText(
    slide,
    "Map match, demand, time basis, calibration and comparison contracts",
    { left: 62, top: 480, width: 520, height: 43 },
    { fontSize: 21.5, color: MUTED },
  );

  addSurface(slide, { left: 629, top: 413, width: 570, height: 119 }, { fill: PALE_BLUE });
  addText(
    slide,
    "EDGE POLICY & QoS",
    { left: 650, top: 433, width: 530, height: 36 },
    { fontSize: 30, bold: true, color: BLUE },
  );
  addText(
    slide,
    "Offload actions, resource ceilings, latency tails and service attainment",
    { left: 650, top: 480, width: 520, height: 43 },
    { fontSize: 21.5, color: MUTED },
  );

  addSurface(
    slide,
    { left: 41, top: 551, width: 1158, height: 88 },
    { geometry: "rect", fill: WHITE, line: LINE, lineWidth: 1, borderRadius: 0 },
  );
  addText(
    slide,
    "LLM DRAFTING SITS OUTSIDE THE EVIDENCE PATH",
    { left: 62, top: 567, width: 1115, height: 34 },
    { fontSize: 26, bold: true, color: BLUE },
  );
  addText(
    slide,
    "It may propose or explain; only signed contracts can execute, and only admitted records can support a claim.",
    { left: 62, top: 605, width: 1115, height: 26 },
    { fontSize: 19, color: MUTED },
  );

  addFooter(slide, 2, "Loop diagram · literature context and repository contracts, not a live-road deployment claim");
  setSources(slide, [
    "Digital-twin loop context: Fuller et al., IEEE Access 2020, DOI 10.1109/ACCESS.2020.2998358; Jones et al., CIRP Journal of Manufacturing Science and Technology 2020, DOI 10.1016/j.cirpj.2020.02.002.",
    "Transport digital-twin context: Wang et al., Transportation Research Part C 2023, DOI 10.1016/j.trc.2023.104014; Nguyen et al., Sustainable Cities and Society 2024, DOI 10.1016/j.scs.2023.104847.",
    "Edge/VEC context: Shi et al., IEEE Internet of Things Journal 2016, DOI 10.1109/JIOT.2016.2579198; Mao et al., IEEE Communications Surveys & Tutorials 2017, DOI 10.1109/COMST.2017.2745201.",
    "Project contracts: docs/architecture.md; docs/experiment_protocol.md; docs/platform/scenario_lifecycle_integration_design.md; docs/platform/decision_safety_layer_design.md.",
    "Source class: literature establishes context; project contracts establish TrafficTwin behaviour. LLM output is explicitly excluded as evidence.",
  ]);
  return slide;
}

function buildEvidence(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = WHITE;
  addSlideTitle(slide, "The headline improves; service does not", 3);

  addText(
    slide,
    "Mean latency by configured per-vehicle RSU concurrency",
    { left: 41, top: 158, width: 565, height: 34 },
    { fontSize: 25, bold: true },
  );
  slide.charts.add("bar", {
    position: { left: 36, top: 195, width: 590, height: 367 },
    categories: ["Capacity 2.5", "Capacity 0.75"],
    series: [
      {
        name: "Mean latency (ms)",
        categories: ["Capacity 2.5", "Capacity 0.75"],
        values: [12027.5, 3716.6],
        fill: BLUE,
      },
    ],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", numberFormatCode: "#,##0.0" },
    chartFill: WHITE,
    chartLine: { style: "solid", fill: WHITE, width: 0 },
    plotAreaFill: { type: "none" },
    plotAreaLine: { style: "solid", fill: WHITE, width: 0 },
    xAxis: {
      visible: true,
      deleted: false,
      line: { style: "solid", fill: LINE, width: 1 },
      textStyle: { typeface: FONT, fontSize: "14px", color: INK },
    },
    yAxis: {
      visible: true,
      deleted: false,
      max: 14000,
      majorUnit: 4000,
      majorGridlines: { style: "solid", fill: "#E8EAF0", width: 1 },
      line: { style: "solid", fill: WHITE, width: 0 },
      textStyle: { typeface: FONT, fontSize: "12px", color: MUTED },
    },
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 90 },
  });

  addText(
    slide,
    "−8,310.9 ms",
    { left: 674, top: 176, width: 515, height: 82 },
    { fontSize: 42, bold: true, color: BLUE },
  );
  addText(
    slide,
    "paired mean · n = 5 · every seed same direction",
    { left: 678, top: 263, width: 500, height: 32 },
    { fontSize: 22, color: MUTED },
  );

  addSurface(slide, { left: 660, top: 310, width: 269, height: 151 }, { fill: LIGHT });
  addText(
    slide,
    "FLAT",
    { left: 682, top: 332, width: 225, height: 45 },
    { fontSize: 36, bold: true },
  );
  addText(
    slide,
    "deadline attainment\nNo service-success gain",
    { left: 682, top: 392, width: 225, height: 54 },
    { fontSize: 21.5, color: MUTED },
  );

  addSurface(slide, { left: 950, top: 310, width: 269, height: 151 }, { fill: PALE_BLUE });
  addText(
    slide,
    "0",
    { left: 972, top: 332, width: 225, height: 45 },
    { fontSize: 38, bold: true, color: BLUE },
  );
  addText(
    slide,
    "ACTION MISMATCHES",
    { left: 972, top: 376, width: 225, height: 27 },
    { fontSize: 20, bold: true, color: BLUE },
  );
  addText(
    slide,
    "8,956,800 decisions\nin each of 9 pilot pairs",
    { left: 972, top: 412, width: 225, height: 42 },
    { fontSize: 21.5, color: MUTED },
  );

  addSurface(
    slide,
    { left: 660, top: 482, width: 559, height: 104 },
    { geometry: "rect", fill: WHITE, line: LINE, lineWidth: 1, borderRadius: 0 },
  );
  addText(
    slide,
    "THE TAIL EXPLAINS THE REVERSAL",
    { left: 682, top: 498, width: 515, height: 32 },
    { fontSize: 27, bold: true },
  );
  addText(
    slide,
    "p50 stayed 44.3 ms; 97.9–99.4% of mass exceeded 1 s. Neither subgroup saw the fleet mean.",
    { left: 682, top: 539, width: 515, height: 40 },
    { fontSize: 19, color: MUTED },
  );

  addFooter(
    slide,
    3,
    "Protocol-confirmed within signed project scope · modelled collapse hour · not causal or real-Manchester validation",
  );
  setSources(slide, [
    "Project measurement: docs/evaluation/capacity_confirmatory_results_20260728.md (arm means 12,027.5 and 3,716.6 ms; paired mean −8,310.9 ms; five seeds; flat deadline attainment).",
    "Project audit: docs/integration/evidence/vec_pilot_keyed_action_comparison_20260728.json (0 mismatches in 8,956,800 keyed decisions for each of nine admitted pilot arm pairs).",
    "Project mechanism: docs/evaluation/offload_partition_analysis_20260729.md and docs/evaluation/capacity_study_detailed_findings.md (p50, tail-mass and subgroup bounds).",
    "Reporting context: Dean and Barroso, Communications of the ACM 2013, DOI 10.1145/2408776.2408794; Nosek et al., Science 2015, DOI 10.1126/science.aab2374; Gorsane et al., NeurIPS Datasets and Benchmarks 2022, DOI 10.52202/068431-0398.",
    "Source class: every number is a project measurement; literature supports tail-aware and protocol-disciplined interpretation only.",
  ]);
  return slide;
}

function buildDecision(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = WHITE;
  addSlideTitle(slide, "Decide what happens next", 4);

  addText(
    slide,
    "Current standing",
    { left: 41, top: 170, width: 530, height: 42 },
    { fontSize: 36, bold: true },
  );

  addText(
    slide,
    "IMPLEMENTED",
    { left: 41, top: 234, width: 230, height: 32 },
    { fontSize: 27, bold: true, color: BLUE },
  );
  addText(
    slide,
    "Auditable instrument, bounded what-if lifecycle, decision-safety and read-only contract browsers.",
    { left: 41, top: 277, width: 540, height: 64 },
    { fontSize: 22 },
  );

  addText(
    slide,
    "BOUNDED EVIDENCE",
    { left: 41, top: 352, width: 275, height: 32 },
    { fontSize: 27, bold: true, color: BLUE },
  );
  addText(
    slide,
    "One signed central result; deviations, refutations and unavailable states remain visible.",
    { left: 41, top: 395, width: 540, height: 64 },
    { fontSize: 22 },
  );

  addText(
    slide,
    "DIRECTION",
    { left: 41, top: 470, width: 210, height: 32 },
    { fontSize: 27, bold: true, color: BLUE },
  );
  addText(
    slide,
    "Signed multi-algorithm portfolio/benchmark, confirmatory mechanism work and Manchester Gate-D—only after their inputs exist.",
    { left: 41, top: 513, width: 555, height: 78 },
    { fontSize: 22 },
  );

  addSurface(slide, { left: 650, top: 164, width: 589, height: 459 }, { fill: LIGHT });
  addText(
    slide,
    "DECISIONS REQUESTED",
    { left: 683, top: 196, width: 510, height: 39 },
    { fontSize: 32, bold: true },
  );
  const questions = [
    {
      top: 278,
      number: "01",
      text: "Gate-D: review the mapping, calibration and comparison contracts—and name the responsible reviewer.",
    },
    {
      top: 386,
      number: "02",
      text: "Approve the next subgroup × matched actor/preset design and its compute envelope before execution.",
    },
    {
      top: 494,
      number: "03",
      text: "Confirm the ethics-gated usability route and the final dissertation scope/reference convention.",
    },
  ];
  questions.forEach((question) => {
    addText(
      slide,
      question.number,
      { left: 683, top: question.top, width: 50, height: 32 },
      { fontSize: 22, bold: true, color: BLUE },
    );
    addText(
      slide,
      question.text,
      { left: 752, top: question.top - 2, width: 445, height: 82 },
      { fontSize: 22 },
    );
  });

  addFooter(
    slide,
    4,
    "Current ceiling: owner-approved candidate where stated · no supervisor, ethics or publication approval inferred",
  );
  setSources(slide, [
    "Current repository standing: docs/implementation-status.md and docs/current_progress_v0_7.md.",
    "Benchmark direction: docs/evaluation/capacity_multi_algorithm_benchmark_predeclaration_20260802.md and docs/platform/capacity_aware_benchmark_design.md.",
    "Manchester Gate-D contracts: docs/integration/manchester_gate_d_integration.md and docs/open-questions.md.",
    "External decision boundary: docs/evaluation/supervisor_contract_decision_form.md and docs/dissertation_evaluation_plan.md.",
    "Source class: project status and unsigned decision materials only. This slide does not record supervisor, ethics, publication, production or real-road approval.",
  ]);
  return slide;
}

export function buildPresentation() {
  const presentation = Presentation.create({
    slideSize: { width: WIDTH, height: HEIGHT },
  });
  buildCover(presentation);
  buildLoop(presentation);
  buildEvidence(presentation);
  buildDecision(presentation);
  return presentation;
}

export async function exportPresentation(outputPath) {
  const presentation = buildPresentation();
  const file = await PresentationFile.exportPptx(presentation);
  await file.save(outputPath);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const outputPath = process.argv[2];
  if (!outputPath) {
    throw new Error("Usage: node traffictwin_supervisor_checkpoint_20260802.mjs <output-pptx>");
  }
  await exportPresentation(path.resolve(outputPath));
  console.log(path.resolve(outputPath));
}
