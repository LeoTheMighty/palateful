import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../core/di/injection.dart';
import '../../core/services/api_client.dart';
import '../../core/services/error_reporter.dart';

/// "Request a change": an admin files one dev request (workstream
/// admin-request-intake, PRD FR-14, calling FR-3's endpoint).
///
/// **Entry.** Opened by route alone: [routePath], no constructor arguments,
/// nothing read from the dashboard. The dashboard tile pushes it, and any
/// other trigger can do the same with
/// `context.push(AdminDevRequestNewScreen.routePath)`, or
/// `appRouter.push(...)` where it has no context under the router. The path
/// sits under `/admin`, so the router's admin redirect guards every entry
/// point, not just the tile. Closing pops back to whoever pushed the
/// screen, with the filed id8 (or null) as the result, or goes to `/admin`
/// when there is nothing to pop (a cold deep link).
///
/// **What the form checks, and what it leaves to the server.** The
/// endpoint normalizes the text (NFKC, drop Cc/Cf except `\n` and `\t`,
/// trim), checks lengths on the normalized text, hashes it and
/// rate-limits. None of that is copied here:
///
/// - Title and body are required: Submit stays disabled until each has a
///   non-whitespace character. That is a strict subset of the server's
///   "blank after normalization" check. Everything Dart's `trim()` empties,
///   the server empties too, so the form never refuses text the server
///   would accept. The converse does not hold (a title made only of
///   zero-width characters), and that case is left to the server's 422.
/// - Lengths: the counters show the server's limits but do not block. The
///   server counts code points after normalization, and no client count
///   matches that: NFKC can lengthen text, while dropping Cf and trimming
///   shorten it. A refusal costs nothing. The 422 is raised before the
///   endpoint runs, so it does not use one of the 5 hourly creates, and
///   the text stays in the form.
/// - Done-when is optional, so a blank one is left out of the call rather
///   than sent and refused.
/// - Errors show the server's own message: 403 and 429 from
///   `error_message`, and each 422 under the field its `loc` names.
class AdminDevRequestNewScreen extends StatefulWidget {
  const AdminDevRequestNewScreen({super.key});

  /// The one place this path is spelled. Router, dashboard tile and any
  /// later trigger all use it.
  static const routePath = '/admin/dev-requests/new';

  /// The server's limits (`TITLE_MAX_LENGTH`, `BODY_MAX_LENGTH`,
  /// `DONE_WHEN_MAX_LENGTH` in `libraries/utils/utils/models/dev_request.py`),
  /// shown on the counters. The widget test pins them to that file.
  static const titleMaxLength = 120;
  static const bodyMaxLength = 4000;
  static const doneWhenMaxLength = 1000;

  /// PRD FR-14's line, shown with the id8 once a request is filed.
  static const filedLine = 'Leo will be asked about it on his laptop.';

  @override
  State<AdminDevRequestNewScreen> createState() =>
      _AdminDevRequestNewScreenState();
}

class _AdminDevRequestNewScreenState extends State<AdminDevRequestNewScreen> {
  static const _genericError = "Couldn't file the request. Try again.";

  /// The request-body fields a 422 `loc` can name.
  static const _fields = {'title', 'body', 'done_when'};

  final _apiClient = getIt<ApiClient>();
  final _title = TextEditingController();
  final _body = TextEditingController();
  final _doneWhen = TextEditingController();

  bool _submitting = false;
  bool _filed = false;
  String? _filedId8;

  /// Server 422 messages keyed by field name.
  final Map<String, String> _fieldErrors = {};
  String? _formError;
  String? _formErrorDetail;

  @override
  void initState() {
    super.initState();
    _title.addListener(() => _onEdited('title'));
    _body.addListener(() => _onEdited('body'));
    _doneWhen.addListener(() => _onEdited('done_when'));
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _doneWhen.dispose();
    super.dispose();
  }

  /// Rebuild for the counters and Submit, and drop the server's message
  /// for a field once it has been edited.
  void _onEdited(String field) {
    if (!mounted) return;
    setState(() => _fieldErrors.remove(field));
  }

  bool get _canSubmit =>
      !_submitting &&
      _title.text.trim().isNotEmpty &&
      _body.text.trim().isNotEmpty;

  Future<void> _submit() async {
    // Also the double-submit guard: one create call per submit.
    if (!_canSubmit) return;
    setState(() {
      _submitting = true;
      _fieldErrors.clear();
      _formError = null;
      _formErrorDetail = null;
    });
    try {
      final response = await _apiClient.createDevRequest(
        title: _title.text,
        body: _body.text,
        doneWhen: _doneWhen.text.trim().isEmpty ? null : _doneWhen.text,
      );
      if (!mounted) return;
      final data = response.data;
      setState(() {
        _submitting = false;
        _filed = true;
        // The row exists (201), so this never falls back to an error:
        // re-filing would create a second one.
        _filedId8 = data is Map ? data['id8']?.toString() : null;
      });
    } on DioException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _applyError(e);
      });
    } catch (e, st) {
      // Not a transport error, so nothing else reports it (the ApiClient
      // interceptor reports 5xx only).
      ErrorReporter.report(e, st, area: 'admin', operation: 'createDevRequest');
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _formError = _genericError;
        _formErrorDetail = ErrorReporter.detail(e);
      });
    }
  }

  /// Map a failed create to what the server said.
  ///
  /// 422 is FastAPI's `{"detail": [{"loc": ["body", <field>], "msg": …}]}`;
  /// 403 and 429 carry `error_message`. The 422 body also echoes the
  /// rejected `input`, which is never shown.
  void _applyError(DioException e) {
    final status = e.response?.statusCode;
    final data = e.response?.data;

    if (status == 422 && data is Map && data['detail'] is List) {
      final unplaced = <String>[];
      for (final item in data['detail'] as List) {
        if (item is! Map) continue;
        final msg = _withoutPrefix(item['msg']?.toString() ?? 'Invalid value');
        final loc = item['loc'];
        final field = loc is List && loc.length >= 2 && loc[0] == 'body'
            ? loc[1]
            : null;
        if (field is String && _fields.contains(field)) {
          _fieldErrors.putIfAbsent(field, () => msg);
        } else {
          unplaced.add(msg);
        }
      }
      if (unplaced.isNotEmpty) {
        _formError = unplaced.join('\n');
      } else if (_fieldErrors.isEmpty) {
        _formError = _genericError;
      }
      return;
    }

    final message = data is Map ? data['error_message'] : null;
    if (status != null &&
        status >= 400 &&
        status < 500 &&
        message is String &&
        message.isNotEmpty) {
      _formError = message;
      return;
    }

    _formError = _genericError;
    _formErrorDetail = ErrorReporter.detail(e);
  }

  /// Pydantic prefixes a validator's message with "Value error, ".
  static String _withoutPrefix(String msg) {
    const prefix = 'Value error, ';
    return msg.startsWith(prefix) ? msg.substring(prefix.length) : msg;
  }

  void _fileAnother() {
    _title.clear();
    _body.clear();
    _doneWhen.clear();
    setState(() {
      _filed = false;
      _filedId8 = null;
      _fieldErrors.clear();
      _formError = null;
      _formErrorDetail = null;
    });
  }

  void _close() {
    final navigator = Navigator.of(context);
    if (navigator.canPop()) {
      navigator.pop(_filedId8);
    } else {
      GoRouter.of(context).go('/admin');
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: Text('Request a change', style: textTheme.titleLarge),
        leading: IconButton(
          key: const Key('dev_request_back_button'),
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
          onPressed: _close,
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: _filed
                ? _buildFiled(colorScheme, textTheme)
                : _buildForm(colorScheme, textTheme),
          ),
        ),
      ),
    );
  }

  Widget _buildForm(ColorScheme colorScheme, TextTheme textTheme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Describe one change. It goes to Leo, who decides whether to '
          'take it on.',
          style: textTheme.bodyMedium?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 20),
        if (_formError != null) ...[
          _buildFormError(colorScheme, textTheme),
          const SizedBox(height: 16),
        ],
        TextField(
          key: const Key('dev_request_title_field'),
          controller: _title,
          enabled: !_submitting,
          maxLength: AdminDevRequestNewScreen.titleMaxLength,
          maxLengthEnforcement: MaxLengthEnforcement.none,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(
            labelText: 'Title',
            hintText: 'One line: what should change',
            errorText: _fieldErrors['title'],
            errorMaxLines: 3,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('dev_request_body_field'),
          controller: _body,
          enabled: !_submitting,
          maxLength: AdminDevRequestNewScreen.bodyMaxLength,
          maxLengthEnforcement: MaxLengthEnforcement.none,
          keyboardType: TextInputType.multiline,
          minLines: 6,
          maxLines: 14,
          decoration: InputDecoration(
            labelText: 'Details',
            hintText: "What's wrong or missing, and why it matters",
            alignLabelWithHint: true,
            errorText: _fieldErrors['body'],
            errorMaxLines: 3,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('dev_request_done_when_field'),
          controller: _doneWhen,
          enabled: !_submitting,
          maxLength: AdminDevRequestNewScreen.doneWhenMaxLength,
          maxLengthEnforcement: MaxLengthEnforcement.none,
          keyboardType: TextInputType.multiline,
          minLines: 2,
          maxLines: 6,
          decoration: InputDecoration(
            labelText: 'Done when (optional)',
            hintText: 'How you will know it is done',
            alignLabelWithHint: true,
            errorText: _fieldErrors['done_when'],
            errorMaxLines: 3,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 20),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            key: const Key('dev_request_submit_button'),
            onPressed: _canSubmit ? _submit : null,
            icon: _submitting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send_outlined),
            label: const Text('File request'),
          ),
        ),
      ],
    );
  }

  Widget _buildFormError(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      key: const Key('dev_request_form_error'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _formError!,
            style: textTheme.bodyMedium?.copyWith(
              color: colorScheme.onErrorContainer,
            ),
          ),
          if (_formErrorDetail != null) ...[
            const SizedBox(height: 6),
            Text(
              _formErrorDetail!,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onErrorContainer,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFiled(ColorScheme colorScheme, TextTheme textTheme) {
    return Column(
      key: const Key('dev_request_filed'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.check_circle_outline, color: colorScheme.primary),
            const SizedBox(width: 8),
            Text('Request filed', style: textTheme.titleLarge),
          ],
        ),
        const SizedBox(height: 16),
        Text(
          'Reference',
          style: textTheme.labelMedium?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        SelectableText(
          _filedId8 ?? '—',
          key: const Key('dev_request_id8'),
          style: textTheme.headlineSmall?.copyWith(
            fontFamily: 'monospace',
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        Text(AdminDevRequestNewScreen.filedLine, style: textTheme.bodyMedium),
        const SizedBox(height: 24),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton(
              key: const Key('dev_request_done_button'),
              onPressed: _close,
              child: const Text('Done'),
            ),
            OutlinedButton(
              key: const Key('dev_request_another_button'),
              onPressed: _fileAnother,
              child: const Text('File another'),
            ),
          ],
        ),
      ],
    );
  }
}
