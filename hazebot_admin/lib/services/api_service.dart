import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:5070/api';
  
  String? _token;
  
  void setToken(String token) {
    _token = token;
  }
  
  void clearToken() {
    _token = null;
  }
  
  Map<String, String> get _headers {
    final headers = {
      'Content-Type': 'application/json',
    };
    
    if (_token != null) {
      headers['Authorization'] = 'Bearer $_token';
    }
    
    return headers;
  }
  
  Future<Map<String, dynamic>> login(String username, String password) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Login failed: ${response.body}');
    }
  }
  
  Future<bool> checkHealth() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
  
  Future<Map<String, dynamic>> getConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load configuration');
    }
  }
  
  Future<Map<String, dynamic>> getGeneralConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/general'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load general configuration');
    }
  }
  
  Future<void> updateGeneralConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/general'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update general configuration');
    }
  }
  
  Future<Map<String, dynamic>> getChannelsConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/channels'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load channels configuration');
    }
  }
  
  Future<void> updateChannelsConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/channels'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update channels configuration');
    }
  }
  
  Future<Map<String, dynamic>> getRolesConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/roles'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load roles configuration');
    }
  }
  
  Future<void> updateRolesConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/roles'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update roles configuration');
    }
  }
  
  Future<Map<String, dynamic>> getMemeConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/meme'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load meme configuration');
    }
  }
  
  Future<void> updateMemeConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/meme'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update meme configuration');
    }
  }
  
  Future<Map<String, dynamic>> getRocketLeagueConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/rocket_league'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load Rocket League configuration');
    }
  }
  
  Future<void> updateRocketLeagueConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/rocket_league'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update Rocket League configuration');
    }
  }
  
  Future<Map<String, dynamic>> getWelcomeConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/welcome'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load welcome configuration');
    }
  }
  
  Future<void> updateWelcomeConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/welcome'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update welcome configuration');
    }
  }
  
  Future<Map<String, dynamic>> getServerGuideConfig() async {
    final response = await http.get(
      Uri.parse('$baseUrl/config/server_guide'),
      headers: _headers,
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load server guide configuration');
    }
  }
  
  Future<void> updateServerGuideConfig(Map<String, dynamic> config) async {
    final response = await http.put(
      Uri.parse('$baseUrl/config/server_guide'),
      headers: _headers,
      body: jsonEncode(config),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to update server guide configuration');
    }
  }
}
