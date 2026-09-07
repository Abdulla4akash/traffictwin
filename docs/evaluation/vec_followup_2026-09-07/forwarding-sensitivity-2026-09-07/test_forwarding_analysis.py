import numpy as np
import pytest

from forwarding_analysis import CHANGED_TASK_FIELDS, exact, transform


def fixture():
    return {
        "task_active":np.array([True,True,True,True,False]),
        "task_type":np.array([0,0,0,0,0],np.int8),
        "task_outcome":np.array([1,2,1,3,0],np.int8),
        "task_forwarded":np.array([True,True,False,False,False]),
        "task_lat_ms":np.array([99.5,1000,99.5,1000,0],np.float32),
        "task_met":np.array([True,False,True,False,False]),
        "task_v2i_admitted":np.array([True,True,False,False,False]),
        "task_forwarding_latency_ms":np.zeros(5,np.float32),
    }


def test_zero_reconstructs_original_fields_exactly():
    data=fixture();got=transform(data,0)
    assert all(exact(got[k],data[k]) for k in CHANGED_TASK_FIELDS)


def test_inclusive_deadline_and_nonforwarded_rejected_inactive_preservation():
    got=transform(fixture(),.5)
    assert got["task_met"].tolist()==[True,False,True,False,False]
    assert got["task_lat_ms"][0]==100
    got=transform(fixture(),1)
    assert got["task_outcome"].tolist()==[2,2,1,3,0]
    assert got["task_lat_ms"][[0,2,3,4]].tolist()==[100.5,99.5,1000,0]


def test_penalty_equal_miss_has_known_outcome_and_unknown_point_latency():
    got=transform(fixture(),10)
    assert np.isnan(got["task_lat_ms"][1])
    assert got["point_latency_ambiguous"].tolist()==[False,True,False,False,False]
    assert got["task_outcome"][1]==2 and not got["task_met"][1]


@pytest.mark.parametrize("cost",[-1,11,float("nan"),float("inf")])
def test_unqualified_cost_rejected(cost):
    with pytest.raises(RuntimeError):transform(fixture(),cost)


def test_already_costed_input_rejected():
    data=fixture();data["task_forwarding_latency_ms"][0]=1
    with pytest.raises(RuntimeError,match="already includes"):transform(data,1)


def test_rejected_forwarded_task_rejected():
    data=fixture();data["task_forwarded"][3]=True
    with pytest.raises(RuntimeError,match="rejected/non-V2I"):transform(data,1)


def test_clip_threshold_guard_rejects_unrecoverable_point():
    data=fixture();data["task_lat_ms"][1]=np.float32(1e8-8)
    with pytest.raises(RuntimeError,match="clipping threshold"):transform(data,10)
