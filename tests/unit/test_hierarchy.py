from fin_table_parser.hierarchy import build_paths, cluster_levels, parent_indices


def test_levels_are_ranks_not_absolute_positions():
    assert cluster_levels([62.3, 75.2, 88.2, 75.1, 62.2]) == [0, 1, 2, 1, 0]
    assert cluster_levels([75.2, 88.2]) == [0, 1]  # a page whose first indent is 75, not 62


def test_close_x_values_share_a_cluster():
    assert cluster_levels([88.2, 89.5, 101.3]) == [0, 0, 1]


def test_paths_disambiguate_repeated_labels():
    labels = ["資産", "有形", "その他", "無形", "その他"]
    paths = build_paths(labels, [0, 1, 2, 1, 2])
    assert paths[2] == ("資産", "有形", "その他")
    assert paths[4] == ("資産", "無形", "その他")


def test_parent_indices():
    assert parent_indices([0, 1, 2, 2, 1, 2]) == [None, 0, 1, 1, 0, 4]
