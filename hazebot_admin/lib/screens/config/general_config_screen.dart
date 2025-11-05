import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/auth_service.dart';
import '../../services/config_service.dart';

class GeneralConfigScreen extends StatefulWidget {
  const GeneralConfigScreen({super.key});

  @override
  State<GeneralConfigScreen> createState() => _GeneralConfigScreenState();
}

class _GeneralConfigScreenState extends State<GeneralConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    
    setState(() => _isLoading = true);
    
    try {
      final config = await authService.apiService.getGeneralConfig();
      
      _controllers['bot_name'] = TextEditingController(
        text: config['bot_name']?.toString() ?? '',
      );
      _controllers['command_prefix'] = TextEditingController(
        text: config['command_prefix']?.toString() ?? '',
      );
      _controllers['presence_update_interval'] = TextEditingController(
        text: config['presence_update_interval']?.toString() ?? '',
      );
      _controllers['message_cooldown'] = TextEditingController(
        text: config['message_cooldown']?.toString() ?? '',
      );
      _controllers['fuzzy_matching_threshold'] = TextEditingController(
        text: config['fuzzy_matching_threshold']?.toString() ?? '',
      );
      
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading config: $e')),
        );
      }
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _saveConfig() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final authService = Provider.of<AuthService>(context, listen: false);
    final configService = Provider.of<ConfigService>(context, listen: false);

    setState(() => _isLoading = true);

    try {
      final config = {
        'bot_name': _controllers['bot_name']!.text,
        'command_prefix': _controllers['command_prefix']!.text,
        'presence_update_interval': int.parse(_controllers['presence_update_interval']!.text),
        'message_cooldown': int.parse(_controllers['message_cooldown']!.text),
        'fuzzy_matching_threshold': double.parse(_controllers['fuzzy_matching_threshold']!.text),
      };

      await configService.updateGeneralConfig(authService.apiService, config);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Configuration saved successfully!')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving config: $e')),
        );
      }
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    for (var controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading && _controllers.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'General Configuration',
              style: Theme.of(context).textTheme.headlineLarge,
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bot Settings',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _controllers['bot_name'],
                      decoration: const InputDecoration(
                        labelText: 'Bot Name',
                        helperText: 'The display name of the bot',
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a bot name';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _controllers['command_prefix'],
                      decoration: const InputDecoration(
                        labelText: 'Command Prefix',
                        helperText: 'Prefix for text commands (e.g., !)',
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a command prefix';
                        }
                        return null;
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Performance Settings',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _controllers['presence_update_interval'],
                      decoration: const InputDecoration(
                        labelText: 'Presence Update Interval (seconds)',
                        helperText: 'How often to update the bot\'s presence status',
                      ),
                      keyboardType: TextInputType.number,
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter an interval';
                        }
                        if (int.tryParse(value) == null) {
                          return 'Please enter a valid number';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _controllers['message_cooldown'],
                      decoration: const InputDecoration(
                        labelText: 'Message Cooldown (seconds)',
                        helperText: 'Cooldown between user messages',
                      ),
                      keyboardType: TextInputType.number,
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a cooldown';
                        }
                        if (int.tryParse(value) == null) {
                          return 'Please enter a valid number';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _controllers['fuzzy_matching_threshold'],
                      decoration: const InputDecoration(
                        labelText: 'Fuzzy Matching Threshold',
                        helperText: 'Similarity threshold for command matching (0.0-1.0)',
                      ),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a threshold';
                        }
                        final num = double.tryParse(value);
                        if (num == null || num < 0 || num > 1) {
                          return 'Please enter a number between 0.0 and 1.0';
                        }
                        return null;
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _saveConfig,
              icon: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save),
              label: const Text('Save Configuration'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
