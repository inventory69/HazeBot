import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../services/config_service.dart';
import 'config/general_config_screen.dart';
import 'config/channels_config_screen.dart';
import 'config/roles_config_screen.dart';
import 'config/meme_config_screen.dart';
import 'config/rocket_league_config_screen.dart';
import 'config/welcome_config_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;
  
  @override
  void initState() {
    super.initState();
    _loadConfig();
  }
  
  Future<void> _loadConfig() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    final configService = Provider.of<ConfigService>(context, listen: false);
    await configService.loadConfig(authService.apiService);
  }

  @override
  Widget build(BuildContext context) {
    final authService = Provider.of<AuthService>(context);
    
    final screens = [
      const DashboardScreen(),
      const GeneralConfigScreen(),
      const ChannelsConfigScreen(),
      const RolesConfigScreen(),
      const MemeConfigScreen(),
      const RocketLeagueConfigScreen(),
      const WelcomeConfigScreen(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('HazeBot Admin'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reload Configuration',
            onPressed: _loadConfig,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Logout',
            onPressed: () {
              authService.logout();
            },
          ),
        ],
      ),
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _selectedIndex,
            onDestinationSelected: (index) {
              setState(() {
                _selectedIndex = index;
              });
            },
            labelType: NavigationRailLabelType.all,
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.dashboard),
                label: Text('Dashboard'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.settings),
                label: Text('General'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.tag),
                label: Text('Channels'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.people),
                label: Text('Roles'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.image),
                label: Text('Memes'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.sports_esports),
                label: Text('Rocket League'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.waving_hand),
                label: Text('Welcome'),
              ),
            ],
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(
            child: screens[_selectedIndex],
          ),
        ],
      ),
    );
  }
}

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ConfigService>(
      builder: (context, configService, _) {
        if (configService.isLoading) {
          return const Center(child: CircularProgressIndicator());
        }
        
        final config = configService.config;
        if (config == null) {
          return const Center(
            child: Text('Failed to load configuration'),
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Dashboard',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 24),
              GridView.count(
                crossAxisCount: 3,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 16,
                crossAxisSpacing: 16,
                children: [
                  _DashboardCard(
                    title: 'Bot Name',
                    value: config['general']?['bot_name'] ?? 'N/A',
                    icon: Icons.smart_toy,
                    color: Colors.blue,
                  ),
                  _DashboardCard(
                    title: 'Mode',
                    value: config['general']?['prod_mode'] == true ? 'Production' : 'Test',
                    icon: Icons.flag,
                    color: config['general']?['prod_mode'] == true 
                        ? Colors.green 
                        : Colors.orange,
                  ),
                  _DashboardCard(
                    title: 'Command Prefix',
                    value: config['general']?['command_prefix'] ?? 'N/A',
                    icon: Icons.terminal,
                    color: Colors.purple,
                  ),
                  _DashboardCard(
                    title: 'Guild ID',
                    value: config['discord_ids']?['guild_id']?.toString() ?? 'N/A',
                    icon: Icons.badge,
                    color: Colors.teal,
                  ),
                  _DashboardCard(
                    title: 'Meme Sources',
                    value: (config['meme']?['meme_sources'] as List?)?.length.toString() ?? '0',
                    icon: Icons.image,
                    color: Colors.pink,
                  ),
                  _DashboardCard(
                    title: 'RL Check Interval',
                    value: '${config['rocket_league']?['rank_check_interval_hours'] ?? 'N/A'}h',
                    icon: Icons.sports_esports,
                    color: Colors.indigo,
                  ),
                ],
              ),
              const SizedBox(height: 32),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.info_outline, 
                               color: Theme.of(context).colorScheme.primary),
                          const SizedBox(width: 8),
                          Text(
                            'Configuration Info',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Use the navigation menu on the left to configure different aspects of the HazeBot. '
                        'All changes are saved automatically to the bot configuration.',
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        '• General: Bot name, command prefix, cooldowns, and thresholds',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      const Text(
                        '• Channels: Discord channel IDs for different features',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      const Text(
                        '• Roles: Discord role IDs for permissions and features',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      const Text(
                        '• Memes: Subreddits, Lemmy communities, and meme sources',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      const Text(
                        '• Rocket League: Rank checking intervals and cache settings',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      const Text(
                        '• Welcome: Rules text and welcome messages',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _DashboardCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _DashboardCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 40, color: color),
            const SizedBox(height: 12),
            Text(
              title,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
