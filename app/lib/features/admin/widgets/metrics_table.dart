import 'package:flutter/material.dart';

import 'latency_sparkline.dart';

/// Generic sortable table for the admin metrics screen.
///
/// Configurable via `columns` so it can render both endpoints and tasks
/// from the same component. Sorting is held by the caller; this widget
/// only surfaces sort intent via `onSortChanged`.
class MetricsTable extends StatelessWidget {
  final List<MetricsTableColumn> columns;
  final List<MetricsTableRow> rows;
  final int sortColumnIndex;
  final bool sortAscending;
  final ValueChanged<({int columnIndex, bool ascending})> onSortChanged;

  const MetricsTable({
    super.key,
    required this.columns,
    required this.rows,
    required this.sortColumnIndex,
    required this.sortAscending,
    required this.onSortChanged,
  });

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 32),
        child: Center(
          child: Text(
            'No samples yet — check back after some traffic.',
          ),
        ),
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        sortColumnIndex: sortColumnIndex,
        sortAscending: sortAscending,
        columns: [
          for (int i = 0; i < columns.length; i++)
            DataColumn(
              label: Text(columns[i].label),
              numeric: columns[i].numeric,
              onSort: columns[i].sortable
                  ? (ci, asc) => onSortChanged((columnIndex: ci, ascending: asc))
                  : null,
            ),
        ],
        rows: [
          for (final row in rows)
            DataRow(
              cells: [
                for (final cell in row.cells)
                  DataCell(
                    cell is _SparklineCellMarker
                        ? LatencySparkline(values: cell.values)
                        : Text(cell.toString()),
                  ),
              ],
            ),
        ],
      ),
    );
  }
}

class MetricsTableColumn {
  final String label;
  final bool numeric;
  final bool sortable;

  const MetricsTableColumn({
    required this.label,
    this.numeric = false,
    this.sortable = true,
  });
}

class MetricsTableRow {
  final List<Object> cells;
  const MetricsTableRow({required this.cells});
}

/// Marker type so callers can put a sparkline into the `cells` list
/// without the table having to sniff types.
class SparklineCell implements _SparklineCellMarker {
  @override
  final List<double> values;
  const SparklineCell(this.values);

  @override
  String toString() => values.toString();
}

abstract class _SparklineCellMarker {
  List<double> get values;
}
