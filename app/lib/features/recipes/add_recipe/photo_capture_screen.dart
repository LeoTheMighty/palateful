import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/theme.dart';
import 'state/import_batches_provider.dart';
import '../../../core/services/error_reporter.dart';
import '../../../shared/widgets/error_banner.dart';

enum _UploadStatus { pending, uploading, complete, failed }

enum _Phase { picking, grouping, submitting }

class _SelectedImage {
  final XFile file;
  final Uint8List bytes;
  String? s3Key;
  _UploadStatus uploadStatus;
  String? uploadError;
  bool previewFailed;

  _SelectedImage({required this.file, required this.bytes})
      : s3Key = null,
        uploadStatus = _UploadStatus.pending,
        uploadError = null,
        previewFailed = false;
}

class PhotoCaptureScreen extends ConsumerStatefulWidget {
  final String? recipeBookId;

  /// Pre-selected image path (sandbox file) from the share-intent flow.
  /// When set, the screen skips its picker sheet and queues the image
  /// for upload immediately. See epic-share-android-entrypoint / sae-2.
  final String? initialPath;

  const PhotoCaptureScreen({
    super.key,
    this.recipeBookId,
    this.initialPath,
  });

  @override
  ConsumerState<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends ConsumerState<PhotoCaptureScreen> {
  final _apiClient = getIt<ApiClient>();
  final _imagePicker = ImagePicker();

  final List<_SelectedImage> _selectedImages = [];
  // Per-image group assignment, keyed by image index. Default = 1 group per image.
  final Map<int, int> _groupAssignments = {};
  final Set<int> _selectedForAssignment = {};

  _Phase _phase = _Phase.picking;
  String? _error;
  String? _errorDetail;

  // Book selection
  String? _selectedBookId;
  List<dynamic> _recipeBooks = [];
  bool _isLoadingBooks = true;

  @override
  void initState() {
    super.initState();
    _selectedBookId = widget.recipeBookId;
    _loadRecipeBooks();
    final seed = widget.initialPath;
    if (seed != null && seed.isNotEmpty && !kIsWeb) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _loadSharedImage(seed));
    }
  }

  Future<void> _loadSharedImage(String path) async {
    try {
      final file = File(path);
      if (!await file.exists()) return;
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      _addImage(
        _SelectedImage(file: XFile(path), bytes: bytes),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Could not open shared image.');
    }
  }

  Future<void> _loadRecipeBooks() async {
    try {
      final response = await _apiClient.getRecipeBooks();
      if (mounted) {
        setState(() {
          _recipeBooks = response.data['items'] ?? [];
          _isLoadingBooks = false;
          if (_selectedBookId == null && _recipeBooks.isNotEmpty) {
            final defaultId = getIt<AuthService>().defaultRecipeBookId;
            if (defaultId != null &&
                _recipeBooks.any((b) => b['id']?.toString() == defaultId)) {
              _selectedBookId = defaultId;
            } else {
              _selectedBookId = _recipeBooks.first['id']?.toString();
            }
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoadingBooks = false);
      }
    }
  }

  // ----------------------------------------------------------------
  // Picking + uploading
  // ----------------------------------------------------------------

  Future<void> _pickFromCamera() async {
    try {
      final image = await _imagePicker.pickImage(
        source: kIsWeb ? ImageSource.gallery : ImageSource.camera,
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 85,
      );
      if (image != null) {
        final bytes = await image.readAsBytes();
        _addImage(_SelectedImage(file: image, bytes: bytes));
      }
    } catch (e) {
      setState(() => _error = 'Failed to capture image: $e');
    }
  }

  Future<void> _pickFromGallery() async {
    try {
      final images = await _imagePicker.pickMultiImage(
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 85,
      );
      for (final image in images) {
        final bytes = await image.readAsBytes();
        _addImage(_SelectedImage(file: image, bytes: bytes));
      }
    } catch (e) {
      setState(() => _error = 'Failed to pick images: $e');
    }
  }

  void _addImage(_SelectedImage img) {
    final newIndex = _selectedImages.length;
    setState(() {
      _selectedImages.add(img);
      _groupAssignments[newIndex] = newIndex; // default 1 group per image
      _error = null;
    });
    _uploadImage(newIndex);
  }

  Future<void> _uploadImage(int index) async {
    if (index >= _selectedImages.length) return;
    final img = _selectedImages[index];
    setState(() {
      img.uploadStatus = _UploadStatus.uploading;
      img.uploadError = null;
    });

    try {
      final uploadUrlResponse =
          await _apiClient.getParserUploadUrl(img.file.name);
      final uploadUrl = uploadUrlResponse.data['upload_url'] as String;
      final s3Key = uploadUrlResponse.data['s3_key'] as String;
      final contentType = uploadUrlResponse.data['content_type'] as String;

      final uploadResponse = await http
          .put(
            Uri.parse(uploadUrl),
            headers: {'Content-Type': contentType},
            body: img.bytes,
          )
          .timeout(const Duration(seconds: 60));

      if (!mounted) return;

      // The image may have been removed while uploading; bail out gracefully.
      if (!_selectedImages.contains(img)) return;

      if (uploadResponse.statusCode != 200) {
        throw Exception('S3 returned ${uploadResponse.statusCode}');
      }

      setState(() {
        img.s3Key = s3Key;
        img.uploadStatus = _UploadStatus.complete;
      });
    } catch (e) {
      if (!mounted) return;
      if (!_selectedImages.contains(img)) return;
      setState(() {
        img.uploadStatus = _UploadStatus.failed;
        img.uploadError = e.toString();
      });
    }
  }

  void _retryUpload(int index) {
    if (index >= _selectedImages.length) return;
    _uploadImage(index);
  }

  void _removeImage(int index) {
    if (index >= _selectedImages.length) return;
    setState(() {
      _selectedImages.removeAt(index);
      // Rebuild group assignments to keep them aligned with image indices
      final old = Map<int, int>.from(_groupAssignments);
      _groupAssignments.clear();
      for (var i = 0; i < _selectedImages.length; i++) {
        final origIdx = i >= index ? i + 1 : i;
        _groupAssignments[i] = old[origIdx] ?? i;
      }
      _selectedForAssignment.clear();
      _compactGroupIndices();
      if (_selectedImages.isEmpty) _phase = _Phase.picking;
    });
  }

  void _showImageSourceDialog() {
    final primaryColor = Theme.of(context).colorScheme.primary;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (!kIsWeb)
                ListTile(
                  leading: Icon(Icons.camera_alt, color: primaryColor),
                  title: const Text('Take Photo'),
                  onTap: () {
                    Navigator.pop(context);
                    _pickFromCamera();
                  },
                ),
              if (kIsWeb)
                ListTile(
                  leading: Icon(Icons.upload_file, color: primaryColor),
                  title: const Text('Upload Photo'),
                  onTap: () {
                    Navigator.pop(context);
                    _pickFromCamera();
                  },
                ),
              ListTile(
                leading: Icon(Icons.photo_library, color: primaryColor),
                title: const Text('Choose from Gallery'),
                subtitle: const Text('Select multiple images'),
                onTap: () {
                  Navigator.pop(context);
                  _pickFromGallery();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ----------------------------------------------------------------
  // Grouping
  // ----------------------------------------------------------------

  bool get _allUploadsComplete =>
      _selectedImages.isNotEmpty &&
      _selectedImages.every((i) => i.uploadStatus == _UploadStatus.complete);

  /// Distinct contiguous group indices (numbered from 0).
  List<int> get _activeGroupIndices {
    final groups = _groupAssignments.values.toSet().toList()..sort();
    return groups;
  }

  int get _recipeCount => _activeGroupIndices.length;

  /// Renumber groups so they form a contiguous 0..N-1 range.
  void _compactGroupIndices() {
    final unique = _groupAssignments.values.toSet().toList()..sort();
    final remap = {for (var i = 0; i < unique.length; i++) unique[i]: i};
    for (final key in _groupAssignments.keys.toList()) {
      _groupAssignments[key] = remap[_groupAssignments[key]!]!;
    }
  }

  void _assignSelectedTo(int targetGroup) {
    setState(() {
      for (final idx in _selectedForAssignment) {
        _groupAssignments[idx] = targetGroup;
      }
      _selectedForAssignment.clear();
      _compactGroupIndices();
    });
  }

  void _addNewGroupAndAssign() {
    if (_selectedForAssignment.isEmpty) return;
    final newGroup = (_groupAssignments.values.fold<int>(-1, (a, b) => a > b ? a : b)) + 1;
    setState(() {
      for (final idx in _selectedForAssignment) {
        _groupAssignments[idx] = newGroup;
      }
      _selectedForAssignment.clear();
      _compactGroupIndices();
    });
  }

  void _toggleSelection(int index) {
    setState(() {
      if (_selectedForAssignment.contains(index)) {
        _selectedForAssignment.remove(index);
      } else {
        _selectedForAssignment.add(index);
      }
    });
  }

  void _enterGrouping() {
    setState(() {
      // Reset to one-group-per-image as the starting point for grouping
      for (var i = 0; i < _selectedImages.length; i++) {
        _groupAssignments[i] = i;
      }
      _selectedForAssignment.clear();
      _phase = _Phase.grouping;
    });
  }

  void _exitGrouping() {
    setState(() {
      _selectedForAssignment.clear();
      _phase = _Phase.picking;
    });
  }

  // ----------------------------------------------------------------
  // Submission
  // ----------------------------------------------------------------

  Future<void> _submitAsOneRecipe() async {
    if (_selectedBookId == null || !_allUploadsComplete) return;
    final items = <Map<String, dynamic>>[
      for (final img in _selectedImages)
        {'s3_key': img.s3Key!, 'group_index': 0},
    ];
    await _submitBatch(items);
  }

  Future<void> _submitGrouped() async {
    if (_selectedBookId == null || !_allUploadsComplete) return;
    final items = <Map<String, dynamic>>[
      for (var i = 0; i < _selectedImages.length; i++)
        {
          's3_key': _selectedImages[i].s3Key!,
          'group_index': _groupAssignments[i] ?? 0,
        },
    ];
    await _submitBatch(items);
  }

  Future<void> _submitBatch(List<Map<String, dynamic>> items) async {
    setState(() {
      _phase = _Phase.submitting;
      _error = null;
    });
    try {
      final response = await _apiClient.createParserBatch(
        recipeBookId: _selectedBookId!,
        items: items,
      );
      final batchId = response.data['id']?.toString();
      if (batchId != null) {
        final notifier = ref.read(importBatchesProvider.notifier);
        notifier.markJustStarted(batchId);
        await notifier.refresh();
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Started import — we'll let you know when it's ready"),
          duration: Duration(seconds: 3),
        ),
      );
      context.pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.picking;
        _error = 'Could not start import: $e';
        _errorDetail = ErrorReporter.detail(e);
      });
    }
  }

  // ----------------------------------------------------------------
  // Build
  // ----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        backgroundColor: colorScheme.surface,
        title: Text(
          _phase == _Phase.grouping ? 'Group photos' : 'Add from Photo',
        ),
        leading: IconButton(
          icon: Icon(_phase == _Phase.grouping ? Icons.arrow_back : Icons.close),
          onPressed: _phase == _Phase.grouping ? _exitGrouping : () => context.pop(),
        ),
      ),
      body: _phase == _Phase.grouping
          ? _buildGroupingView()
          : _buildPickingView(),
    );
  }

  Widget _buildPickingView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildImageSection(),
          const SizedBox(height: 16),
          _buildBookSelector(),
          const SizedBox(height: 16),
          _buildSubmitSection(),
          if (_error != null) ...[
            const SizedBox(height: 16),
            _buildErrorSection(),
          ],
        ],
      ),
    );
  }

  Widget _buildBookSelector() {
    if (_isLoadingBooks) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_recipeBooks.isEmpty) {
      return Text(
        'No recipe books available. Create one first.',
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      );
    }
    return DropdownButtonFormField<String>(
      initialValue: _selectedBookId,
      decoration: const InputDecoration(
        labelText: 'Destination Book',
        prefixIcon: Icon(Icons.book_outlined),
        border: OutlineInputBorder(),
      ),
      items: _recipeBooks.map((book) {
        return DropdownMenuItem<String>(
          value: book['id']?.toString(),
          child: Text(book['name'] ?? 'Untitled'),
        );
      }).toList(),
      onChanged: _phase == _Phase.submitting
          ? null
          : (value) => setState(() => _selectedBookId = value),
    );
  }

  Widget _buildImageSection() {
    if (_selectedImages.isEmpty) {
      final colorScheme = Theme.of(context).colorScheme;
      return GestureDetector(
        onTap: _showImageSourceDialog,
        child: Container(
          height: 300,
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: colorScheme.secondary.withValues(alpha: 0.3),
              width: 2,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.add_photo_alternate_outlined, size: 64, color: colorScheme.secondary),
              const SizedBox(height: 12),
              Text(
                'Tap to select images',
                style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 16),
              ),
              const SizedBox(height: 4),
              Text(
                'Take a photo or choose multiple from gallery',
                style: TextStyle(color: context.appColors.textTertiary, fontSize: 14),
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '${_selectedImages.length} image${_selectedImages.length == 1 ? '' : 's'} selected',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: Theme.of(context).colorScheme.onSurface,
              ),
            ),
            TextButton.icon(
              onPressed: _phase == _Phase.submitting ? null : _showImageSourceDialog,
              icon: const Icon(Icons.add_photo_alternate, size: 20),
              label: const Text('Add more'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 160,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: _selectedImages.length,
            itemBuilder: (context, index) => _buildImageThumbnail(index),
          ),
        ),
      ],
    );
  }

  Widget _buildImageThumbnail(int index) {
    final img = _selectedImages[index];
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Stack(
        children: [
          Container(
            width: 120,
            height: 160,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: colorScheme.secondary.withValues(alpha: 0.3)),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(11),
              child: img.previewFailed
                  ? _buildThumbnailFallback(img)
                  : Image.memory(
                      img.bytes,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (!img.previewFailed) {
                            setState(() => img.previewFailed = true);
                          }
                        });
                        return _buildThumbnailFallback(img);
                      },
                    ),
            ),
          ),
          // Upload status overlay
          Positioned.fill(
            child: _buildUploadOverlay(img, index),
          ),
          if (_phase != _Phase.submitting)
            Positioned(
              top: 4,
              right: 4,
              child: GestureDetector(
                onTap: () => _removeImage(index),
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: const BoxDecoration(
                    color: Colors.black54,
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.close, size: 16, color: Colors.white),
                ),
              ),
            ),
          Positioned(
            bottom: 4,
            left: 4,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${index + 1}',
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadOverlay(_SelectedImage img, int index) {
    switch (img.uploadStatus) {
      case _UploadStatus.complete:
        return Align(
          alignment: Alignment.bottomRight,
          child: Padding(
            padding: const EdgeInsets.all(6),
            child: Container(
              padding: const EdgeInsets.all(2),
              decoration: const BoxDecoration(
                color: Colors.green,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check, size: 14, color: Colors.white),
            ),
          ),
        );
      case _UploadStatus.failed:
        return GestureDetector(
          onTap: () => _retryUpload(index),
          child: Container(
            color: Colors.black.withValues(alpha: 0.45),
            child: const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.error_outline, color: Colors.white, size: 28),
                  SizedBox(height: 4),
                  Text('Tap to retry',
                      style: TextStyle(color: Colors.white, fontSize: 11)),
                ],
              ),
            ),
          ),
        );
      case _UploadStatus.uploading:
      case _UploadStatus.pending:
        return Container(
          color: Colors.black.withValues(alpha: 0.25),
          child: const Center(
            child: SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            ),
          ),
        );
    }
  }

  Widget _buildThumbnailFallback(_SelectedImage img) {
    final extension = img.file.name.split('.').last.toUpperCase();
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      color: colorScheme.surfaceContainerHighest,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.image, size: 32, color: colorScheme.secondary),
            const SizedBox(height: 4),
            Text(extension, style: TextStyle(fontSize: 12, color: context.appColors.textTertiary)),
          ],
        ),
      ),
    );
  }

  Widget _buildSubmitSection() {
    if (_selectedImages.isEmpty) return const SizedBox.shrink();
    final canSubmit = _allUploadsComplete &&
        _selectedBookId != null &&
        _phase != _Phase.submitting;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ElevatedButton(
          onPressed: canSubmit ? _submitAsOneRecipe : null,
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 16),
            backgroundColor: Theme.of(context).colorScheme.primary,
            foregroundColor: Theme.of(context).colorScheme.onPrimary,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: _phase == _Phase.submitting
              ? const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    ),
                    SizedBox(width: 12),
                    Text('Starting import...'),
                  ],
                )
              : const Text(
                  'Import as one recipe',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
        ),
        if (_selectedImages.length > 1) ...[
          const SizedBox(height: 8),
          TextButton(
            onPressed: canSubmit ? _enterGrouping : null,
            child: const Text('These are separate recipes →'),
          ),
        ],
        if (!_allUploadsComplete && _selectedImages.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            'Waiting for uploads to finish...',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: context.appColors.textTertiary,
              fontSize: 12,
            ),
          ),
        ],
      ],
    );
  }

  // ----------------------------------------------------------------
  // Grouping view
  // ----------------------------------------------------------------

  Widget _buildGroupingView() {
    final colorScheme = Theme.of(context).colorScheme;
    final groups = _activeGroupIndices;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Row(
            children: [
              const Icon(Icons.menu_book_outlined, size: 18),
              const SizedBox(width: 6),
              Text(
                'Will create $_recipeCount recipe${_recipeCount == 1 ? '' : 's'}',
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w600),
              ),
              const Spacer(),
              if (_selectedForAssignment.isNotEmpty)
                Text(
                  '${_selectedForAssignment.length} selected',
                  style: TextStyle(
                    color: colorScheme.primary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            'Tap images to select, then tap a recipe chip to assign them.',
            style: TextStyle(
              color: context.appColors.textTertiary,
              fontSize: 12,
            ),
          ),
        ),
        Expanded(
          child: GridView.builder(
            padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
              childAspectRatio: 0.8,
            ),
            itemCount: _selectedImages.length,
            itemBuilder: (context, index) => _buildGroupingTile(index),
          ),
        ),
        _buildChipRow(groups),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: ElevatedButton(
              onPressed: _phase == _Phase.submitting ? null : _submitGrouped,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                backgroundColor: colorScheme.primary,
                foregroundColor: colorScheme.onPrimary,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: _phase == _Phase.submitting
                  ? const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        ),
                        SizedBox(width: 12),
                        Text('Starting import...'),
                      ],
                    )
                  : Text(
                      'Create $_recipeCount recipe${_recipeCount == 1 ? '' : 's'}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: _buildErrorSection(),
          ),
      ],
    );
  }

  Widget _buildGroupingTile(int index) {
    final img = _selectedImages[index];
    final colorScheme = Theme.of(context).colorScheme;
    final isSelected = _selectedForAssignment.contains(index);
    final groupIndex = _groupAssignments[index] ?? index;
    final recipeNumber = groupIndex + 1;

    return GestureDetector(
      onTap: () => _toggleSelection(index),
      child: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: isSelected
                    ? colorScheme.primary
                    : colorScheme.secondary.withValues(alpha: 0.3),
                width: isSelected ? 3 : 1,
              ),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: img.previewFailed
                  ? _buildThumbnailFallback(img)
                  : Image.memory(
                      img.bytes,
                      fit: BoxFit.cover,
                      width: double.infinity,
                      height: double.infinity,
                    ),
            ),
          ),
          Positioned(
            top: 4,
            left: 4,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: colorScheme.primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Recipe $recipeNumber',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
          if (isSelected)
            Positioned(
              top: 4,
              right: 4,
              child: Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  color: colorScheme.primary,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check, size: 14, color: Colors.white),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildChipRow(List<int> groups) {
    final colorScheme = Theme.of(context).colorScheme;
    final hasSelection = _selectedForAssignment.isNotEmpty;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: colorScheme.outlineVariant, width: 0.5),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            for (final g in groups)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ActionChip(
                  label: Text('Recipe ${g + 1}'),
                  backgroundColor: hasSelection
                      ? colorScheme.primaryContainer
                      : colorScheme.surfaceContainerHighest,
                  onPressed: hasSelection ? () => _assignSelectedTo(g) : null,
                ),
              ),
            ActionChip(
              avatar: const Icon(Icons.add, size: 16),
              label: const Text('New recipe'),
              backgroundColor: hasSelection
                  ? colorScheme.primaryContainer
                  : colorScheme.surfaceContainerHighest,
              onPressed: hasSelection ? _addNewGroupAndAssign : null,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorSection() {
    final appColors = context.appColors;
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: appColors.errorLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colorScheme.error.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: colorScheme.error),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _error!,
              style: TextStyle(color: colorScheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
