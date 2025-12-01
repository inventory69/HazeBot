# Contributing to HazeWorldBot

Thank you for your interest in contributing to HazeWorldBot! 🌿

We welcome contributions from the community. Whether it's bug fixes, new features, documentation improvements, or performance optimizations, your help is appreciated!

---

## 📋 Getting Started

### Prerequisites

Before contributing, make sure you have:
- **Python 3.8+** installed
- **Git** for version control
- A **Discord Bot Token** for testing
- Familiarity with **discord.py** and **async/await** patterns

### Setting Up Your Development Environment

1. **Fork the Repository**
   ```bash
   git clone https://github.com/yourusername/HazeWorldBot.git
   cd HazeWorldBot
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install ruff  # For code formatting and linting
   ```

4. **Configure Environment**
   - Copy `.env.example` to `.env`
   - Add your test bot token and configuration
   - Update `Config.py` with your test server IDs

---

## 🔧 Development Workflow

### 1. Create a Feature Branch

Always work on a separate branch:
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Follow the existing code style and patterns
- Use **async/await** throughout (no blocking calls)
- Add comments for complex logic
- Update docstrings for new functions/classes

### 3. Code Quality

We use **ruff** for code formatting and linting:

```bash
# Format your code
ruff format .

# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### 4. Test Your Changes

- Test in a development Discord server
- Ensure all commands work as expected
- Verify permissions and error handling
- Check that no existing functionality breaks

### 5. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git commit -m "feat: add new leaderboard category"
git commit -m "fix: resolve ticket deletion issue"
git commit -m "docs: update command reference"
```

**Commit Message Conventions:**
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding tests
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub with:
- **Clear title** describing the change
- **Description** of what was changed and why
- **Testing steps** for reviewers to verify

---

## 📝 Coding Guidelines

### Code Style

- **PEP 8** compliance (enforced by ruff)
- **Type hints** for function parameters and return values
- **Descriptive variable names** (no single-letter variables except in loops)
- **Docstrings** for all public functions and classes

### Project Structure

```
HazeWorldBot/
├── Cogs/              # Feature modules (one Cog per feature)
├── Utils/             # Shared utilities (Logger, Embeds, Cache)
├── Data/              # JSON data storage (gitignored)
├── Config.py          # Central configuration
└── Main.py            # Bot entry point
```

### Async Best Practices

- **Always use async/await** for I/O operations
- Use `asyncio.gather()` for parallel operations
- Don't use `time.sleep()` - use `asyncio.sleep()` instead
- Handle async context managers properly (`async with`)

### Error Handling

```python
try:
    # Your code
    await some_async_operation()
except discord.Forbidden:
    Logger.error("Missing permissions")
except Exception as e:
    Logger.error(f"Unexpected error: {e}")
```

### Discord.py Patterns

- **Defer interactions** for long-running operations
- Use **embeds** for rich responses
- Implement **proper permission checks**
- Add **autocomplete** for slash commands where applicable
- Use **views and modals** for interactive UI

### 🧩 Command Implementation Pattern

**IMPORTANT: Avoid Code Duplication Between Prefix and Slash Commands**

Both prefix commands (`!command`) and slash commands (`/command`) should share the same logic through helper functions.

**❌ Bad Example (Code Duplication):**
```python
@commands.command(name="example")
async def example_prefix(self, ctx: commands.Context):
    # Logic here...
    embed = discord.Embed(title="Example", description="Result")
    await ctx.send(embed=embed)

@app_commands.command(name="example")
async def example_slash(self, interaction: discord.Interaction):
    # Same logic duplicated...
    embed = discord.Embed(title="Example", description="Result")
    await interaction.response.send_message(embed=embed)
```

**✅ Good Example (Shared Helper Function):**
```python
async def handle_example(self, user: discord.User) -> discord.Embed:
    """Shared logic for both prefix and slash commands."""
    # Core logic here...
    embed = discord.Embed(title="Example", description="Result")
    return embed

@commands.command(name="example")
async def example_prefix(self, ctx: commands.Context):
    embed = await self.handle_example(ctx.author)
    await ctx.send(embed=embed)

@app_commands.command(name="example")
async def example_slash(self, interaction: discord.Interaction):
    embed = await self.handle_example(interaction.user)
    await interaction.response.send_message(embed=embed)
```

**Benefits:**
- Single source of truth for command logic
- Easier to maintain and test
- Consistent behavior across prefix and slash commands
- Reduces bugs from code duplication

**See Examples:**
- `TodoList.py`: `handle_todo_update()` and `handle_todo_show()`
- `Profile.py`: Shared profile generation logic
- `Leaderboard.py`: Shared leaderboard generation

---

## 🎯 What to Contribute

### High Priority
- **Bug fixes** - Always welcome!
- **Performance improvements** - Especially caching and optimization
- **Documentation** - README, docstrings, comments
- **Error handling** - Better error messages and recovery

### Feature Ideas
- New leaderboard categories
- Additional moderation tools
- Enhanced ticket system features
- More Rocket League integrations
- Improved logging and monitoring

### Before Starting Large Features
- **Open an issue** to discuss the feature
- Get feedback on the approach
- Ensure it aligns with the bot's purpose

---

## 🧪 Testing

### Manual Testing Checklist
- [ ] Commands work with both `/` and `!` prefix
- [ ] Permissions are correctly enforced
- [ ] Error messages are user-friendly
- [ ] Embeds display correctly
- [ ] No console errors or warnings
- [ ] Data is properly saved/loaded

### Test in Your Development Server
Create a test Discord server with:
- Admin, moderator, and member roles
- Test channels for tickets, welcomes, etc.
- Multiple test users/accounts

---

## 📞 Getting Help

- **Questions?** Open an issue with the `question` label
- **Bug reports?** Use the bug report template
- **Feature requests?** Use the feature request template

---

## 📄 Code of Conduct

- Be respectful and constructive
- Help others learn and improve
- Focus on what's best for the community
- Accept constructive criticism gracefully

---

## 📄 License

By contributing, you agree that your contributions will be licensed under the same MIT License that covers the project.

---

**Thank you for contributing to HazeWorldBot!** 🌿💖