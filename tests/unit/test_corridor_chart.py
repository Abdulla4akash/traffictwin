from __future__ import annotations

from traffictwin.canonical.records import IncidentRecord, VehicleStateRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ui.charts import corridor_figure, corridor_snapshot_rows


def test_corridor_figure_uses_only_coordinate_history_up_to_replay_time() -> None:
    tables = CanonicalTables(
        vehicles=[
            VehicleStateRecord(
                source_file="vehicle_state.csv",
                source_row=2,
                timestamp_s=0,
                vehicle_id="v1",
                x=0,
                y=1,
            ),
            VehicleStateRecord(
                source_file="vehicle_state.csv",
                source_row=3,
                timestamp_s=10,
                vehicle_id="v1",
                x=5,
                y=1,
            ),
            VehicleStateRecord(
                source_file="vehicle_state.csv",
                source_row=4,
                timestamp_s=20,
                vehicle_id="v1",
                x=10,
                y=1,
            ),
        ],
        incidents=[
            IncidentRecord(
                source_file="incidents.csv",
                source_row=2,
                incident_id="i1",
                timestamp_s=5,
                incident_type="synthetic_closure",
                location="corridor-a",
                duration_s=20,
            )
        ],
    )

    rows = corridor_snapshot_rows(tables, 10)
    figure = corridor_figure(tables, 10)

    assert len(rows) == 2
    assert figure is not None
    assert len(figure.data) == 2
    assert list(figure.data[0].x) == [0, 5]
    assert figure.layout.annotations[0].text.startswith("Active incident metadata")


def test_corridor_figure_is_unavailable_without_complete_coordinates() -> None:
    tables = CanonicalTables(
        vehicles=[
            VehicleStateRecord(
                source_file="vehicle_state.csv",
                source_row=2,
                timestamp_s=0,
                vehicle_id="v1",
            )
        ]
    )

    assert corridor_figure(tables, 0) is None
