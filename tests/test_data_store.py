"""Tests for bleplot.data_store"""
import pytest
from bleplot.data_store import ScrollingData, DataStore
from bleplot.theme import PLOT_COLORS_F


class TestScrollingData:
    def test_add_point_below_max(self):
        sd = ScrollingData(identifier=0, max_size=5)
        sd.add_point(0.0, 1.0)
        sd.add_point(1.0, 2.0)
        assert len(sd.data) == 2

    def test_circular_wrap(self):
        sd = ScrollingData(identifier=0, max_size=3)
        for i in range(5):
            sd.add_point(float(i), float(i * 10))
        # Buffer holds last 3 points (indices 2,3,4 → values 20,30,40)
        assert len(sd.data) == 3
        ordered = sd.ordered()
        ys = [p[1] for p in ordered]
        assert ys == [20.0, 30.0, 40.0]

    def test_latest_value(self):
        sd = ScrollingData(identifier=0, max_size=10)
        sd.add_point(0.0, 99.0)
        assert sd.latest_value() == 99.0
        sd.add_point(1.0, 77.0)
        assert sd.latest_value() == 77.0

    def test_xs_ys(self):
        sd = ScrollingData(identifier=0, max_size=10)
        sd.add_point(1.0, 10.0)
        sd.add_point(2.0, 20.0)
        assert sd.xs() == [1.0, 2.0]
        assert sd.ys() == [10.0, 20.0]

    def test_ordered_after_wrap(self):
        sd = ScrollingData(identifier=0, max_size=4)
        for i in range(6):
            sd.add_point(float(i), float(i))
        ordered = sd.ordered()
        xs = [p[0] for p in ordered]
        assert xs == sorted(xs), "ordered() should return chronological order"


class TestDataStore:
    def test_append_creates_variables(self):
        ds = DataStore()
        ds.append_all_data([1.0, 2.0, 3.0], 0.0)
        ids = ds.identifiers()
        assert sorted(ids) == [0, 1, 2]

    def test_auto_color_assigned(self):
        ds = DataStore()
        ds.append_all_data([0.0, 0.0], 0.0)
        _, info, _, _ = ds.copy_for_render()
        assert info[0].color == PLOT_COLORS_F[0]
        assert info[1].color == PLOT_COLORS_F[1]

    def test_data_flowing_flag(self):
        ds = DataStore()
        assert not ds.data_flowing
        ds.append_all_data([1.0], 0.0)
        assert ds.data_flowing

    def test_update_info(self):
        ds = DataStore()
        ds.append_all_data([1.0], 0.0)
        ds.update_info(0, name="MyVar", color=(1.0, 0.0, 0.0, 1.0))
        _, info, _, _ = ds.copy_for_render()
        assert info[0].name == "MyVar"
        assert info[0].color == (1.0, 0.0, 0.0, 1.0)

    def test_reset_clears_all(self):
        ds = DataStore()
        ds.append_all_data([1.0, 2.0], 0.0)
        ds.reset()
        assert ds.identifiers() == []
        assert not ds.data_flowing

    def test_copy_for_render_is_safe(self):
        ds = DataStore()
        ds.append_all_data([1.0], 0.0)
        data, info, lines, flowing = ds.copy_for_render()
        # Mutating the snapshot should not affect the store
        data[0].data.append((999.0, 999.0))
        data2, _, _, _ = ds.copy_for_render()
        assert len(data2[0].data) == 1

    def test_print_buffer(self):
        ds = DataStore()
        for i in range(250):
            ds.push_raw_line(f"line {i}")
        _, _, lines, _ = ds.copy_for_render()
        assert len(lines) == 200  # maxlen
        assert lines[-1] == "line 249"
