import 'package:flutter/foundation.dart';
import 'api_service.dart';

class ConfigService extends ChangeNotifier {
  Map<String, dynamic>? _config;
  bool _isLoading = false;
  
  Map<String, dynamic>? get config => _config;
  bool get isLoading => _isLoading;
  
  Future<void> loadConfig(ApiService apiService) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      _config = await apiService.getConfig();
    } catch (e) {
      debugPrint('Error loading config: $e');
      _config = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateGeneralConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateGeneralConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating general config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateChannelsConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateChannelsConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating channels config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateRolesConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateRolesConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating roles config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateMemeConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateMemeConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating meme config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateRocketLeagueConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateRocketLeagueConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating Rocket League config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  Future<void> updateWelcomeConfig(ApiService apiService, Map<String, dynamic> config) async {
    _isLoading = true;
    notifyListeners();
    
    try {
      await apiService.updateWelcomeConfig(config);
      await loadConfig(apiService);
    } catch (e) {
      debugPrint('Error updating welcome config: $e');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
