Upgrade a skill in Claude World.

First, check the current skill levels and available tokens:
```
python3 $CLAUDE_PROJECT_DIR/hooks/game_client.py skills
```

Based on the results, if the user specified a skill to upgrade, run:
```
python3 $CLAUDE_PROJECT_DIR/hooks/game_client.py upgrade <skill>
```

Where <skill> is one of: reading, writing, searching, building

Upgrade costs are 50 tokens per current level (level 1 costs 50, level 2 costs 100, etc.).

If the user didn't specify which skill, show them their current skills with costs and ask which one they want to upgrade.

Display the result of the upgrade (success or failure message).
