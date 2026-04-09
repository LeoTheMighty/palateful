import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';

class AdminErrorDetailScreen extends StatefulWidget {
  final String errorId;

  const AdminErrorDetailScreen({super.key, required this.errorId});

  @override
  State<AdminErrorDetailScreen> createState() => _AdminErrorDetailScreenState();
}

class _AdminErrorDetailScreenState extends State<AdminErrorDetailScreen> {
  final _apiClient = getIt<ApiClient>();

  bool _isLoading = true;
  String? _error;
  Map<String, dynamic> _errorData = {};

  @override
  void initState() {
    super.initState();
    _fetchErrorDetail();
  }

  Future<void> _fetchErrorDetail() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await _apiClient.getAdminErrorDetail(widget.errorId);
      if (!mounted) return;

      setState(() {
        _errorData = response.data as Map<String, dynamic>;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load error detail: $e';
        _isLoading = false;
      });
    }
  }

  void _copyStackTrace() {
    final stackTrace = _errorData['stack_trace'] as String? ?? '';
    if (stackTrace.isNotEmpty) {
      Clipboard.setData(ClipboardData(text: stackTrace));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Stack trace copied to clipboard')),
      );
    }
  }

  String _formatTimestamp(String? timestamp) {
    if (timestamp == null) return 'N/A';
    try {
      final dt = DateTime.parse(timestamp);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
    } catch (_) {
      return timestamp;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Error Detail', style: textTheme.titleLarge),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 64, color: colorScheme.error),
                      const SizedBox(height: 16),
                      Text(_error!, style: textTheme.bodyMedium, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: _fetchErrorDetail,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : _buildContent(colorScheme, textTheme),
    );
  }

  Widget _buildContent(ColorScheme colorScheme, TextTheme textTheme) {
    final errorType = _errorData['error_type'] as String? ?? 'Unknown';
    final errorMessage = _errorData['error_message'] as String? ?? '';
    final errorCode = _errorData['error_code'] as String?;
    final method = _errorData['method'] as String? ?? '';
    final path = _errorData['path'] as String? ?? '';
    final statusCode = _errorData['status_code'];
    final userId = _errorData['user_id'] as String?;
    final requestId = _errorData['request_id'] as String?;
    final createdAt = _errorData['created_at'] as String?;
    final stackTrace = _errorData['stack_trace'] as String? ?? '';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Error type header
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  errorType,
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onErrorContainer,
                  ),
                ),
                if (errorMessage.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    errorMessage,
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onErrorContainer,
                    ),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Details
          _buildDetailRow('Error Code', errorCode ?? 'N/A', textTheme, colorScheme),
          _buildDetailRow('Method', method, textTheme, colorScheme),
          _buildDetailRow('Path', path, textTheme, colorScheme),
          _buildDetailRow('Status Code', statusCode?.toString() ?? 'N/A', textTheme, colorScheme),
          _buildDetailRow('User ID', userId ?? 'N/A', textTheme, colorScheme),
          _buildDetailRow('Request ID', requestId ?? 'N/A', textTheme, colorScheme),
          _buildDetailRow('Created At', _formatTimestamp(createdAt), textTheme, colorScheme),

          const SizedBox(height: 24),

          // Stack trace
          if (stackTrace.isNotEmpty) ...[
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Stack Trace',
                  style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                ),
                TextButton.icon(
                  onPressed: _copyStackTrace,
                  icon: const Icon(Icons.copy, size: 16),
                  label: const Text('Copy'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey.shade900,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: SelectableText(
                  stackTrace,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: Colors.white70,
                    height: 1.5,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildDetailRow(
    String label,
    String value,
    TextTheme textTheme,
    ColorScheme colorScheme,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: SelectableText(
              value,
              style: textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
