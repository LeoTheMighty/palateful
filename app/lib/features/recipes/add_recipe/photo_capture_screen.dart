import 'dart:async';
import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;

import '../../../core/di/injection.dart';
import '../../../core/services/api_client.dart';
import '../../../core/services/auth_service.dart';
import '../../../core/theme/theme.dart';

class _SelectedImage {
  final XFile file;
  final Uint8List bytes;
  bool previewFailed;

  // ignore: unused_element_parameter
  _SelectedImage({required this.file, required this.bytes, this.previewFailed = false});
}

class _JobResult {
  final String jobId;
  final String inputKey;
  String status; // submitted, running, succeeded, failed
  String? extractedText;
  String? error;

  // ignore: unused_element_parameter
  _JobResult({required this.jobId, required this.inputKey, this.status = 'submitted'});
}

class PhotoCaptureScreen extends StatefulWidget {
  final String? recipeBookId;

  const PhotoCaptureScreen({super.key, this.recipeBookId});

  @override
  State<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends State<PhotoCaptureScreen> {
  final _apiClient = getIt<ApiClient>();
  final _imagePicker = ImagePicker();

  final List<_SelectedImage> _selectedImages = [];
  String _status = 'idle'; // idle, uploading, submitting, polling, succeeded, failed, structuring, previewing
  final List<_JobResult> _jobResults = [];
  String? _error;
  Timer? _pollTimer;
  Timer? _importPollTimer;
  int _ocrPollCount = 0;
  static const _maxOcrPolls = 60; // 5 minutes at 5s intervals

  // Book selection
  String? _selectedBookId;
  List<dynamic> _recipeBooks = [];
  bool _isLoadingBooks = true;

  // Import pipeline state
  String? _importJobId;
  Map<String, dynamic>? _importItem;
  Map<String, dynamic>? _parsedRecipe;
  bool _isApproving = false;

  @override
  void initState() {
    super.initState();
    _selectedBookId = widget.recipeBookId;
    _loadRecipeBooks();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _importPollTimer?.cancel();
    super.dispose();
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
            if (defaultId != null && _recipeBooks.any((b) => b['id']?.toString() == defaultId)) {
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
        setState(() {
          _selectedImages.add(_SelectedImage(file: image, bytes: bytes));
          _resetResults();
        });
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
      if (images.isNotEmpty) {
        for (final image in images) {
          final bytes = await image.readAsBytes();
          _selectedImages.add(_SelectedImage(file: image, bytes: bytes));
        }
        setState(() => _resetResults());
      }
    } catch (e) {
      setState(() => _error = 'Failed to pick images: $e');
    }
  }

  void _resetResults() {
    _jobResults.clear();
    _error = null;
    _status = 'idle';
    _importJobId = null;
    _importItem = null;
    _parsedRecipe = null;
  }

  void _removeImage(int index) {
    setState(() {
      _selectedImages.removeAt(index);
      _resetResults();
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

  Future<void> _processImages() async {
    if (_selectedImages.isEmpty || _selectedBookId == null) return;

    setState(() {
      _status = 'uploading';
      _error = null;
      _jobResults.clear();
    });

    try {
      // Upload all images and collect their S3 keys
      final s3Keys = <String>[];

      for (int i = 0; i < _selectedImages.length; i++) {
        final img = _selectedImages[i];

        // Get presigned upload URL
        final uploadUrlResponse = await _apiClient.getParserUploadUrl(img.file.name);
        final uploadUrl = uploadUrlResponse.data['upload_url'] as String;
        final s3Key = uploadUrlResponse.data['s3_key'] as String;
        final contentType = uploadUrlResponse.data['content_type'] as String;

        // Upload image to S3 with timeout
        debugPrint('Uploading image ${i + 1} (${img.bytes.length} bytes) to S3...');
        debugPrint('Upload URL host: ${Uri.parse(uploadUrl).host}');
        final http.Response uploadResponse;
        try {
          uploadResponse = await http.put(
            Uri.parse(uploadUrl),
            headers: {'Content-Type': contentType},
            body: img.bytes,
          ).timeout(const Duration(seconds: 60));
        } catch (uploadError) {
          debugPrint('S3 upload failed: $uploadError');
          throw Exception('Image upload failed: $uploadError');
        }

        debugPrint('S3 upload response: ${uploadResponse.statusCode}');
        if (uploadResponse.statusCode != 200) {
          debugPrint('S3 error body: ${uploadResponse.body.substring(0, (uploadResponse.body.length).clamp(0, 500))}');
          throw Exception('Image upload returned ${uploadResponse.statusCode}');
        }

        s3Keys.add(s3Key);
      }

      // Submit job(s)
      setState(() => _status = 'submitting');

      if (s3Keys.length == 1) {
        final submitResponse = await _apiClient.submitParserJob(s3Keys.first);
        final jobId = submitResponse.data['id'] as String;
        setState(() {
          _jobResults.add(_JobResult(jobId: jobId, inputKey: s3Keys.first));
          _status = 'polling';
        });
      } else {
        final submitResponse = await _apiClient.submitBatchParserJob(s3Keys);
        final jobs = submitResponse.data['jobs'] as List;
        setState(() {
          for (final job in jobs) {
            _jobResults.add(_JobResult(
              jobId: job['id'] as String,
              inputKey: job['input_s3_key'] as String,
            ));
          }
          _status = 'polling';
        });
      }

      _startOcrPolling();
    } catch (e) {
      setState(() {
        _status = 'failed';
        _error = 'Processing failed: $e';
      });
    }
  }

  void _startOcrPolling() {
    _pollTimer?.cancel();
    _ocrPollCount = 0;
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (timer) async {
      _ocrPollCount++;
      if (_ocrPollCount > _maxOcrPolls) {
        timer.cancel();
        if (mounted) {
          setState(() {
            _status = 'failed';
            _error = 'OCR processing timed out. Please try again.';
          });
        }
        return;
      }

      bool allDone = true;

      for (final job in _jobResults) {
        if (job.status == 'succeeded' || job.status == 'failed') continue;

        try {
          final response = await _apiClient.getParserJob(job.jobId);
          final status = response.data['status'] as String;

          setState(() {
            job.status = status;
            if (status == 'succeeded') {
              job.extractedText = response.data['extracted_text'] as String?;
            } else if (status == 'failed') {
              job.error = response.data['error_message'] as String? ?? 'Job failed';
            }
          });

          if (status != 'succeeded' && status != 'failed') {
            allDone = false;
          }
        } catch (e) {
          allDone = false;
          debugPrint('Polling error for job ${job.jobId}: $e');
        }
      }

      if (allDone) {
        timer.cancel();
        if (!mounted) return;
        final anySucceeded = _jobResults.any((j) => j.status == 'succeeded');
        if (anySucceeded) {
          _startImportPipeline();
        } else {
          setState(() {
            _status = 'failed';
            _error = 'OCR processing failed for all images.';
          });
        }
      }
    });
  }

  Future<void> _startImportPipeline() async {
    setState(() => _status = 'structuring');

    // Collect OCR texts from succeeded jobs
    final ocrTexts = _jobResults
        .where((j) => j.status == 'succeeded' && j.extractedText != null)
        .map((j) => j.extractedText!)
        .toList();

    if (ocrTexts.isEmpty) {
      setState(() {
        _status = 'failed';
        _error = 'No text was extracted from the images.';
      });
      return;
    }

    try {
      final response = await _apiClient.startImport(
        _selectedBookId!,
        sourceType: 'photo',
        ocrTexts: ocrTexts,
      );
      if (!mounted) return;

      _importJobId = response.data['id']?.toString();
      _startImportPolling();
    } catch (e) {
      if (mounted) {
        setState(() {
          _status = 'failed';
          _error = 'Could not start recipe structuring. Please try again.';
        });
      }
    }
  }

  void _startImportPolling() {
    _importPollTimer?.cancel();
    _importPollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _pollImportJob();
    });
  }

  Future<void> _pollImportJob() async {
    if (_importJobId == null) return;

    try {
      final response = await _apiClient.getImportJob(_importJobId!);
      if (!mounted) return;

      final status = response.data['status']?.toString();

      if (status == 'awaiting_review' || status == 'completed') {
        _importPollTimer?.cancel();
        await _loadImportItems();
      } else if (status == 'failed') {
        _importPollTimer?.cancel();
        setState(() {
          _status = 'failed';
          _error = 'Could not structure recipe from OCR text.';
        });
      }
    } catch (e) {
      // Keep polling on transient errors
    }
  }

  Future<void> _loadImportItems() async {
    if (_importJobId == null) return;

    try {
      final response = await _apiClient.listImportItems(_importJobId!);
      if (!mounted) return;

      final items = response.data['items'] as List? ?? [];
      if (items.isNotEmpty) {
        final item = items.first;
        setState(() {
          _importItem = item;
          _parsedRecipe = item['parsed_recipe'] as Map<String, dynamic>?;
          _status = 'previewing';
        });
      } else {
        setState(() {
          _status = 'failed';
          _error = 'No recipe data was extracted from the photos.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _status = 'failed';
          _error = 'Could not load extracted recipe. Please try again.';
        });
      }
    }
  }

  Future<void> _approveImport() async {
    if (_isApproving || _importItem == null) return;

    final itemId = _importItem!['id']?.toString();
    if (itemId == null) return;

    setState(() => _isApproving = true);
    try {
      HapticFeedback.selectionClick();
      await _apiClient.approveImportItem(itemId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Recipe imported successfully!')),
        );
        context.pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save recipe. Please try again.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isApproving = false);
    }
  }

  Future<void> _skipImport() async {
    if (_importItem == null) return;
    final itemId = _importItem!['id']?.toString();
    if (itemId == null) return;

    try {
      await _apiClient.skipImportItem(itemId);
    } catch (_) {}
    if (mounted) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        backgroundColor: colorScheme.surface,
        title: const Text('Add from Photo'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: _parsedRecipe != null
          ? _buildRecipePreview()
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildImageSection(),
                  const SizedBox(height: 16),
                  _buildBookSelector(),
                  const SizedBox(height: 16),
                  _buildProcessButton(),
                  const SizedBox(height: 16),
                  _buildStatusIndicator(),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    _buildErrorSection(),
                  ],
                ],
              ),
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
      value: _selectedBookId,
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
      onChanged: _status == 'idle' ? (value) {
        setState(() => _selectedBookId = value);
      } : null,
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
              onPressed: _status == 'idle' ? _showImageSourceDialog : null,
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
          if (_status == 'idle')
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

  Widget _buildProcessButton() {
    final isProcessing = _status != 'idle' && _status != 'failed' && _status != 'succeeded';

    final label = _selectedImages.length <= 1
        ? 'Extract Recipe with AI'
        : 'Extract Recipe from ${_selectedImages.length} Photos';

    return ElevatedButton(
      onPressed: _selectedImages.isNotEmpty && !isProcessing && _selectedBookId != null
          ? _processImages
          : null,
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 16),
        backgroundColor: Theme.of(context).colorScheme.primary,
        foregroundColor: Theme.of(context).colorScheme.onPrimary,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      child: isProcessing
          ? Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                ),
                const SizedBox(width: 12),
                Text(_getProcessingText()),
              ],
            )
          : Text(
              label,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
    );
  }

  String _getProcessingText() {
    switch (_status) {
      case 'uploading':
        return 'Uploading images...';
      case 'submitting':
        return 'Submitting OCR job...';
      case 'polling':
        final done = _jobResults.where((j) => j.status == 'succeeded' || j.status == 'failed').length;
        return 'Reading text ($done/${_jobResults.length})...';
      case 'structuring':
        return 'Structuring recipe...';
      default:
        return 'Processing...';
    }
  }

  Widget _buildStatusIndicator() {
    final appColors = context.appColors;
    final colorScheme = Theme.of(context).colorScheme;
    IconData icon;
    Color color;
    String text;

    switch (_status) {
      case 'uploading':
        icon = Icons.cloud_upload;
        color = appColors.info;
        text = 'Uploading ${_selectedImages.length} image${_selectedImages.length == 1 ? '' : 's'}...';
        break;
      case 'submitting':
        icon = Icons.send;
        color = appColors.info;
        text = 'Submitting OCR job...';
        break;
      case 'polling':
        icon = Icons.hourglass_empty;
        color = appColors.warning;
        final done = _jobResults.where((j) => j.status == 'succeeded' || j.status == 'failed').length;
        text = 'Reading text ($done/${_jobResults.length} complete)... This may take a minute.';
        break;
      case 'structuring':
        icon = Icons.auto_awesome;
        color = appColors.info;
        text = 'AI is structuring your recipe...';
        break;
      case 'succeeded':
        icon = Icons.check_circle;
        color = appColors.success;
        text = 'Recipe extracted successfully!';
        break;
      case 'failed':
        icon = Icons.error;
        color = colorScheme.error;
        text = _error ?? 'Processing failed';
        break;
      default:
        icon = Icons.info_outline;
        color = appColors.textTertiary;
        text = 'Select images and tap "Extract Recipe"';
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: TextStyle(color: color, fontWeight: FontWeight.w500),
            ),
          ),
        ],
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

  Widget _buildRecipePreview() {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final name = _parsedRecipe!['name'] ?? 'Untitled Recipe';
    final description = _parsedRecipe!['description'] as String?;
    final imageUrl = _parsedRecipe!['image_url'] as String?;
    final ingredients = _parsedRecipe!['ingredients'] as List? ?? [];
    final instructions = _parsedRecipe!['instructions'] as String?;
    final prepTime = _parsedRecipe!['prep_time_minutes'];
    final cookTime = _parsedRecipe!['cook_time_minutes'];
    final servings = _parsedRecipe!['servings'];
    final extractorUsed = _parsedRecipe!['extractor_used'] as String?;

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Extracted badge
              Row(
                children: [
                  Icon(Icons.auto_awesome, size: 16, color: colorScheme.primary),
                  const SizedBox(width: 4),
                  Text(
                    'Extracted from photo via ${extractorUsed ?? 'AI'}',
                    style: textTheme.labelSmall?.copyWith(
                      color: colorScheme.primary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Image
              if (imageUrl != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: CachedNetworkImage(
                    imageUrl: imageUrl,
                    height: 200,
                    width: double.infinity,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
              if (imageUrl != null) const SizedBox(height: 16),

              // Name
              Text(
                name,
                style: textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              if (description != null) ...[
                const SizedBox(height: 8),
                Text(
                  description,
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],

              // Metadata
              if (prepTime != null || cookTime != null || servings != null) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  children: [
                    if (prepTime != null)
                      Chip(
                        avatar: const Icon(Icons.timer_outlined, size: 16),
                        label: Text('Prep ${prepTime}m'),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (cookTime != null)
                      Chip(
                        avatar: const Icon(Icons.local_fire_department_outlined, size: 16),
                        label: Text('Cook ${cookTime}m'),
                        visualDensity: VisualDensity.compact,
                      ),
                    if (servings != null)
                      Chip(
                        avatar: const Icon(Icons.people_outline, size: 16),
                        label: Text('Serves $servings'),
                        visualDensity: VisualDensity.compact,
                      ),
                  ],
                ),
              ],

              // Ingredients
              if (ingredients.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'Ingredients (${ingredients.length})',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                ...ingredients.map((ing) {
                  final text = ing is Map ? (ing['text'] ?? '') : ing.toString();
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('  \u2022  ', style: textTheme.bodyMedium),
                        Expanded(
                          child: Text(text, style: textTheme.bodyMedium),
                        ),
                      ],
                    ),
                  );
                }),
              ],

              // Instructions
              if (instructions != null && instructions.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'Instructions',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(instructions, style: textTheme.bodyMedium),
              ],

              const SizedBox(height: 32),
            ],
          ),
        ),

        // Bottom action bar
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                OutlinedButton(
                  onPressed: _isApproving ? null : _skipImport,
                  child: const Text('Skip'),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _isApproving ? null : _approveImport,
                    icon: _isApproving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.check),
                    label: const Text('Save Recipe'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
