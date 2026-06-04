# r/PurePoolPro — Engagement Analysis & Opportunity Map

**Data Source:** Reddit API via reddit-skills (Chrome extension bridge, logged in as grundell)
**Scrape Date:** June 4, 2026
**Posts Analyzed:** ~15 unique posts (subreddit is very small)

## Community Size Assessment
- ~15-20 visible posts across hot/new/top sorts
- Very small community (single-digit upvotes typical)
- Most active period: May 2026 (Patch 3 launch window)
- Ripstone official account (u/RipstoneGames) posts regularly but gets modest engagement
- Subreddit is essentially a mirror of Discord activity

## All Posts (sorted by score)

| Post | Score | Comments | Author | Category |
|------|-------|----------|--------|----------|
| 3rd Place May POTM (DarthThug) | 7 | 1 | RipstoneGames | Community event |
| Friend Code Mega Thread | 5 | 4 | Community | **Matchmaking** |
| April POTM Results | 8 | 20 | RipstoneGames | Community event |
| May POTM Compilation | 7 | 2 | RipstoneGames | Community event |
| Golf (clip) | 7 | 2 | Community | Gameplay |
| Rules Reminder | 7 | 6 | RipstoneGames | Official comms |
| May POTM Launch | 6 | 4 | RipstoneGames | Community event |
| Great Update | 5 | 5 | Community | Feedback |
| Doubles (clip) | 4 | 0 | Community | Gameplay |
| FOV Request | 4 | 3 | Community | Feature request |
| Fluke clip | 4 | 1 | Community | Gameplay |
| 3 Rail Bank clip | 4 | 5 | Community | Gameplay |
| Steam Reviews plea | 4 | 13 | Community | **Pain point** |
| POTM Reminder | 3 | 2 | RipstoneGames | Community event |
| Newer Player Q | 3 | 2 | Community | Discussion |
| Still Not Perfect | 3 | 4 | Community | Feedback |
| Speed Up Shot | 3 | 2 | Community | Feature request |
| Matchmaking PS5 | 2 | 6 | Community | **Pain point** |
| Black screen online | 0 | 0 | Community | **Bug** |
| Why do you lose when opponent takes too long? | 1 | 0 | Community | **Pain point** |

## Key Insights

### 1. POTM is the ONLY engagement driver
- 5 of 19 posts are POTM-related
- POTM posts get 7-8 upvotes vs 0-4 for everything else
- April POTM got 20 comments (highest) — community LOVES this
- Ripstone uses Reddit for POTM announcements

### 2. Matchmaking is broken
- Friend Code Mega Thread exists because there's no in-game solution
- "Matchmaking PS5" post has 6 comments — all complaints
- "Black screen online" post — 0 upvotes but critical bug

### 3. Slow play is a Reddit complaint too
- "Why do you lose when an opponent takes too long?" — confirms Discord finding
- This is a cross-platform pain point

### 4. Steam Reviews plea
- "Steam Reviews plea" got 13 comments — community wants better visibility
- Players actively trying to market the game

### 5. Feature requests
- FOV customization
- Speed up shot option
- Both also mentioned in Discord suggestions channel

## Reddit vs Discord Cross-Reference

| User | Reddit | Discord | Notes |
|------|--------|---------|-------|
| RipstoneGames | ✅ Posts POTM | ✅ Active (208 msgs) | Official account |
| DarthThug | ✅ POTM winner | ✅ Power user (181 msgs) | Bank shot specialist |
| AGallonOfCat | ✅ Comments | ❌ Not in Discord | Reddit-only |

## Opportunities (Reddit-specific)

| Opportunity | Evidence | Fit |
|-------------|----------|-----|
| **POTM Cross-posting** | Ripstone posts on Reddit, could auto-cross-post to Discord | High engagement content |
| **Friend Code Directory** | Mega thread exists, no bot support | Matchmaking workaround |
| **Bug Report Aggregation** | Black screen, slow play reported on both platforms | Unified tracker |
| **Steam Review Campaign** | Community actively pleading for reviews | Bot could remind/encourage |
| QOL Suggestions | 2 | 2 | Feature request |
| Trick Shot | 2 | 1 | Gameplay |
| Daily Clearance | 2 | 2 | Bug |
| Why lose on timeout? | 1 | 6 | Bug |
| Xbox? | 1 | 13 | **High interest** |
| Break-off Error | 1 | 4 | Bug |
| Game Crashes | 1 | 4 | Bug |
| Haptic Feedback | 1 | 8 | Bug |
| Black Screen of Doom | 0 | 16 | **TOP PAIN POINT** |
| AI Rail Shots | 0 | 5 | Feedback |
| AI… Again | 0 | 12 | **Recurring complaint** |
| Black Screen (2nd) | 0 | 4 | Bug |

## Key Insight: The Silent Majority Problem

Posts with 0 upvotes but HIGH comment counts indicate frustrated users who aren't upvoting — they're just reporting problems:
- Black screen: 0 upvotes, 16 comments (MOST DISCUSSED ISSUE)
- AI behavior: 0 upvotes, 12 comments
- Xbox release: 1 upvote, 13 comments (HIGH DEMAND, no info)
- Haptic feedback: 1 upvote, 8 comments

## Pain Point Categories (by frequency)

### 1. ONLINE/MULTIPLAYER ISSUES (highest impact)
- Black screen when joining online games (3+ posts, 20+ comments total)
- Matchmaking takes forever (75% of time searching)
- Break-off sequence wrong in local play
- Lose when opponent takes too long (timeout = loss is bad UX)

### 2. AI COMPLAINTS (recurring theme)
- AI plays rail shots instead of simple pots (2 posts, 17 comments)
- JudCasper68 is a repeat complainer — engaged but frustrated

### 3. MISSING FEATURES
- No Xbox release date (13 comments, no answer from Ripstone)
- No doubles mode (requested)
- No speed-up/fast-forward after shot
- No table view preferences
- FOV not disclosed
- Haptic feedback broke after update

### 4. BUGS
- Game crashes (repeatable: Daily Challenge → menu → back = crash)
- Haptic feedback stopped working
- 9-ball replacement when spot occupied
- Daily clearance bug

## What Gets Engagement (Ripstone's Content)

| Content Type | Avg Upvotes | Avg Comments | Notes |
|-------------|-------------|--------------|-------|
| POTM Results/Compilations | 7.5 | 1.5 | Highest upvotes — community loves this |
| POTM Launch/Reminder | 4.5 | 3 | Good engagement |
| Official rules/comms | 6 | 9.5 | Mixed — some controversy |
| Gameplay clips (community) | 3-4 | 2-5 | Decent engagement |
| Bug reports | 0-1 | 4-16 | Low upvotes, HIGH comments |

## Opportunity Assessment for Cuebot

### HIGH PRIORITY — Direct Pain Points You Can Solve

| Opportunity | Evidence | Your Fit |
|------------|----------|----------|
| **Matchmaking Bot** | Friend Code Mega Thread (5↑, 4💬), Matchmaking PS5 (2↑, 6💬), 75% time searching | You built Challonge + match management. A Discord lobby system with skill/timezone matching directly addresses this |
| **Tournament System** | POTM is manual (submit clips on social). Community loves POTM (7+ upvotes). No bracket system exists | You already have Challonge integration. Automated brackets with in-game verification |
| **Bug Tracker / Feedback Hub** | 6+ bug posts with no structured tracking. Black screen has 16 comments across 3 posts with no resolution visible | Discord channel that aggregates, categorizes, tracks status. Community wants this |
| **Leaderboard Bot** | Patch 3 added Ranked mode with global leaderboards. No way to view rankings outside game | Discord bot that pulls and displays rankings by mode/difficulty |

### MEDIUM PRIORITY — Community Building

| Opportunity | Evidence | Your Fit |
|------------|----------|----------|
| **Friend Code Directory** | Ripstone just started Mega Thread (June 2). Manual, unsearchable | Bot-managed directory: search by platform/skill/timezone. Natural evolution of their thread |
| **Content Aggregation** | Gameplay clips scattered across Reddit. Darth-Thug posts regularly but gets 0-4 upvotes | Discord channel that auto-aggregates top clips, gives creators visibility |
| **New Player Onboarding** | "Newer player" post, "Great update" post — new players arriving post-Patch 3 | Welcome bot, FAQ, skill-based matching for beginners |

### LOW PRIORITY — Nice to Have

| Opportunity | Evidence | Your Fit |
|------------|----------|----------|
| **Xbox Release Tracker** | 13 comments on "Xbox?" post, no answer | News aggregation bot (low effort, high community value) |
| **AI Behavior Feedback** | 2 posts, 17 comments — passionate but niche | Feedback channel to devs (community wants voice heard) |

## Discord Intelligence (#chat-pure-pool-pro)

### Participants (active in sampled conversation)

| User | Role | Messages | Notes |
|------|------|----------|-------|
| **mmm** | Moderator | 4 | Helps with POTM uploads, offers Google Drive workaround |
| **Ripstone Em** | Developer | 3 | Responds within hours, asks follow-ups, values video evidence |
| **eeriearcade** | Player | 3 | Submits POTM clips, reports bugs with video |
| .:DarthThug:. | Player | 2 | Helps others with PlayStation video upload limits |
## Discord Server Analysis (#chat-pure-pool-pro)

**Dataset:** 1000 messages | April 13 – June 4, 2026 | 46 unique speakers | 408 replies (40.8%) | 361 messages with reactions (36.1%)

### Community Activity Overview

**Monthly growth:** April 356 msgs → May 564 msgs → June (partial) 80 msgs
**Weekly peak:** W20 (May 12-18) with 203 messages — Patch 3 hype week

**Top 10 Most Active:**
| User | Messages | Reactions | Role |
|------|----------|-----------|------|
| .:DarthThug:. | 166 | 50 | Player (bank shot specialist, slow play) |
| Rob Bro | 105 | 52 | Player (community joker, "Apples" caller) |
| Ripstone | 104 | 111 | MOD/Publisher (highest reactions) |
| eeriearcade | 104 | 64 | Player (quality voice, 80+ hrs) |
| IAmLucifee | 86 | 27 | Player (leaderboard critic) |
| Queenie Lucy II | 81 | 42 | Player (timezone nerd, joker) |
| Aurakite | 77 | 70 | Player (POTM runner, community defender) |
| JAMBO--C | 49 | 40 | Player (snooker enthusiast) |
| Lemmy9 | 24 | 17 | Player |
| OvercookedOctopusFeet | 23 | 25 | Player (block function advocate) |
| Ripstone Em | 20 | 28 | DEV (technical, responsive) |

**Ripstone team total: 124 messages (12.4% of all messages)**

### What the Discord conversations reveal

**Channel:** #chat-pure-pool-pro | **Also referenced:** #bug-reports-pure-pool-pro, #suggestions-pure-pool-pro, #info

**1. POTM Submission is Broken**
- Google form → no video preview
- Google Drive → no video preview in Discord
- Discord upload → compresses quality (5MB limit)
- Moderator (mmm) manually helps players upload via their personal Google Drive
- No native video submission system exists
- Aurakite (who runs POTM) is in the channel — confirmed direct contact
- Ripstone: "Need to shift more units so we can afford Discord Nitro and raise that upload cap"
- Ripstone: "Compress it into a 10mb 5fps gif and we'll try and make sense of it!"
- POTM expanding: "We're gonna open it up across more channels for the next one"
- POTM judging: 3 judges from dev team, each scores entries

**2. Dev is Active and Responsive**
- Ripstone Em responds within hours to bug reports
- Asks follow-up questions in real-time
- Provides detailed technical explanations (e.g. "Cueing discrepancy issue")
- Ripstone Em: "Nearly 1500 hours in and I still struggle with Pro. I've got the biggest respect for the folks that play on nothing but Pro"
- Ripstone Em: "I had to complete the clearance 10 times each on Steam and PS5 to repro/check the fix"
- Ripstone team: 124 messages in 2 months = ~2 messages/day average
- Ripstone team reads DMs but asks players to use public channels: "DMs aren't usually the right avenue — it's just one of us running the community"

**3. Bug Reporting is Understaffed**
- ONE person collects ALL bug reports, ONE person reproduces for devs
- "There simply isn't enough time in the day to personally respond to every single report"
- Bug reproduction is #1 bottleneck — live build vs dev build mismatch
- Ripstone Em: "issues seen on the live build have to be reproduced in the developer environment (which is actually a slightly different build)"
- Structured reproduction steps are EXTREMELY valuable to them

**4. Ranked/Leaderboard System Explained**
- Ripstone Em: "It weighs total games won first and then by win ratio. We didn't want people to play only one match, win and sit on 100%"
- Player confusion persists: Rob Bro (15th, 33%), IAmLucifee (19th, 90%)
- Villa1tez1972 proposes ELO system with break-and-clear bonuses
- Ripstone: "We've got a fair bit of experience with Elo-style systems from our previous chess games" —但他们说 playerbase too small for proper ELO matching
- Ripstone: "It's a really compelling system - but falls apart a bit if the playerbase isn't yet big enough"

**5. Cross-Progression Not Coming**
- Ripstone: "Cross-progression is one of those features we'd love to see in every game in an ideal world... But for a team of our size it's not feasible right now"
- Explicitly deprioritized

**6. Slow Play / Deliberate Stalling**
- DarthThug takes 60 seconds per shot using screen cues (names, clock, background images)
- "Apples" player: "takes about 40-45 seconds per shot, will circumvent the table at least twice"
- eeriearcade: "Opponent afk for 20-30 seconds nearly every shot is painful"
- Villa1tez1972: "spent 55secs literally letting his cue spin in circles before he quit"
- Players using block function to avoid stalling opponents
- DarthThug proposes: "ability to set it to 30 sec 45 sec or 60 sec shot timer would be amazing"

**7. Xbox Version Targeting Spring 2026**
- Ripstone: "Still targeting Spring 2026, and we'll post everywhere as soon as there's an exact date"
- "Spring runs right up to 21st June"
- 8 Ball frustrated: "At this point it's unfair to us Xbox users"
- Ripstone: "porting the game to Xbox is a substantial chunk of work with separate technical and certification requirements"

**8. Snooker DLC Confirmed**
- Ripstone: "Snooker currently in development alongside the Xbox Port"
- "Planned for 2026... expect it to follow not too long after the Xbox release"
- 35 mentions in dataset — high community interest
- Pocket sounds requested: "make them pockets snooker-sound"

**9. Steam Deck Nearly Verified**
- Ripstone: "text scaling is one of the only things stopping us getting that official 'Steam Deck Verified' tag"
- "Unfortunately a tricky one to achieve with our engine/UI"

**10. Community Self-Policing on Cheating**
- Rob Bro publicly accuses someone of cheating
- Aurakite: "report them directly rather than berating them in public"
- Ripstone: "Please keep your thoughts in the thread! But when you see specific examples we'd really appreciate a form about it"
- No anti-cheat system — entirely manual

**11. Platform Video Limitations**
- Discord: 5MB upload limit, heavy compression
- PS5: 3min video capture limit
- Ripstone: "Yeah 10mb - still not enough for any decent quality/length"

**12. Known Bugs**
- Cross-play bug (Steam ↔ PS5, build 2084) — reproduced June 4
- Daily Clearance streak resets at 27 days — first report
- Killer numbering bug — "known bug, thankfully numbering isn't of any importance in this mode"
- PS5 crash — programmer investigating network issues
- Plant shot not getting star — Phil Elliott (Ripstone employee) reports it himself

**13. Patch 3 Features (May 2026)**
- Ranked Game mode (evolved from "Quick Game")
- Push outs in 9-ball
- Lag to break
- Individual leaderboards per mode/difficulty
- "Any" collective board with weighted wins at higher difficulties

### #questions-and-suggestions-pure-pool-pro Analysis

**Dataset:** 1000 messages | Nov 9, 2025 – Jun 2, 2026 | 85 unique speakers | 396 replies (39.6%) | 317 with reactions (31.7%)

**Monthly spike:** Feb 2026 had 494 messages (launch month!) → Mar 238 → Apr 105 → May 76

**Top contributors:** Ripstone (104), Aurakite (100), JAMBO--C (91), OvercookedOctopusFeet (64), Rob Bro (51), eltorofire6996 (50)

**Topic breakdown (by mention count):**
| Topic | Count | Insight |
|-------|-------|---------|
| Table/Cue Customization | 138 | HIGHEST — players want more customization options |
| Online/Lag | 71 | Persistent concern |
| Snooker DLC | 60 | High anticipation |
| Ranked/Leaderboard | 59 | Confusion about mechanics |
| POTM/Competition | 59 | Community loves tournaments |
| Bug Reports | 43 | Cross-platform issues dominate |
| Music/Audio | 37 | Players want music DLC |
| Xbox Release | 32 | Frustration building |
| Career Mode | 28 | Suggestions for improvement |
| Shot Mechanics | 25 | Diamond system, practice mode |
| Graphics/Performance | 22 | Lighting, FPS, optimization |
| Block Feature | 19 | Players using it to avoid stallers |
| Matchmaking | 17 | Queue while playing career/training |
| Player Behaviour | 8 | Sportsmanship discussions |
| Daily Clearance | 9 | Practice mode requests |

**Key Ripstone insights from suggestions channel:**
- "We pulled together plans for our Week 1 and Month 1 patches within 24hrs of launch, all thanks to feedback on that very form"
- "VooFoo is now defunct - but a lot of our team are the very same guys that worked on the original!"
- "The team that worked on Hustle Kings back then was actually substantially bigger than what we've got now!"
- Xbox Series S struggling: "that lack of RAM is gonna take some work to get around"
- "our programming team is a little leaner than usual at the moment"
- Camera choice: "we've made a deliberate choice not to include Broadcast-style cameras"
- "500+ messages a day at the moment across all the channels" during launch week
- Baize colours: "we build and test our table colours under specific lighting so that balls stay as readable as possible"
- Cross-progression: "no plans at this time" but "get it down on a form"
- AI behaviour hotfix shipped Week 1 post-launch
- "We genuinely considered a Just Stop Oil gradient baize design for Snooker"

### Key Discord-Specific Opportunities

| Opportunity | Evidence | Fit |
|------------|----------|-----|
| **POTM Submission Bot** | Manual process, mod helping individually, quality loss from Discord compression. 59 msgs about POTM. Expanding to more platforms | Automate collection, external hosting for quality video, thumbnail generation, dedup tracking |
| **Bug Report Tracker** | Dev values video evidence, no structured tracking, status unknown to community. ONE person handles all reports. Reproduction is #1 bottleneck. 43 bug msgs in suggestions | Discord form → categorize (mode/platform/severity) → link video → status pipeline. Structured reproduction steps = gold for dev |
| **Video Sharing Helper** | PS 3min limit, Discord compression, no cross-platform workflow. "Compress it into a 10mb 5fps gif" | Auto-trim bot, platform-specific advice, Google Drive preview links |
| **Friend Code Directory** | Reddit Mega Thread exists, Discord is where players actually talk. 4 friend code mentions | Searchable directory by platform/skill/timezone |
| **Matchmaking Queue** | 17 msgs — players want to queue while playing career/training. "A great example is pure pool original. As you were at the practice table while searching" | Background queue system, notification when match found |
| **Table/Cue Customization Hub** | 138 msgs — HIGHEST topic. Players want more customization | Custom table designer, cue gallery, community voting on new designs |
| **Shot Timer Monitor** | DarthThug (60s/shot), "Apples" (40-45s), players using block to avoid stallers. 19 block msgs | Track avg shot time per player, flag chronic slow players, customizable shot timers |
| **Leaderboard Dashboard** | 59 msgs — players confused about ranking (33% vs 90% win rates), system opacity | Pull ranked data, show transparent ELO breakdown, historical performance |
| **Cheat Report System** | Public accusations happening, no anti-cheat, no structured reporting | Anonymous report channel with evidence attachment, pattern detection |
| **Xbox Welcome Bot** | 32 msgs — Xbox players frustrated, Series S struggling with RAM. "At this point it's unfair to us Xbox users" | Auto-welcome Xbox players, timeline updates, cross-platform friend matching |
| **Music/Audio DLC** | 37 msgs — players want music DLC. "Will there be a DLC available in the future with the music?" | Partner with music artists, in-game playlist manager |
| **Career Mode Enhancer** | 28 msgs — suggestions for AI difficulty, practice mode, shot retake | AI behavior customizer, practice mode with shot positioning |
| **Daily Clearance Tracker** | 9 msgs — streak tracking, practice at lower difficulties | Streak dashboard, practice mode unlock, daily challenge analytics |

## Competitive Landscape

- No existing Discord bot for Pure Pool Pro
- Ripstone links to discord.gg/ripstone (their main Discord, not game-specific)
- The subreddit IS the de facto community hub — small but active
- Ripstone is responsive on BOTH Reddit (u/RipstoneGames) and Discord (Ripstone Em)
- No automated tools for any community function (POTM, bug tracking, matchmaking, leaderboards)

## Recommended Pitch to Ripstone

**Offer: Pure Pool Pro Community Discord Bot Suite**

1. **Matchmaking & Lobbies** — Skill-based, timezone-aware matchmaking to solve the #1 complaint (black screen + long queue times)
2. **Tournament Brackets** — Automated POTM-style tournaments with Challonge integration
3. **Leaderboards** — Pull Ranked mode data into Discord with transparent ELO breakdown
4. **Bug Tracker** — Structured feedback with reproduction steps (their #1 bottleneck is reproducing bugs)
5. **Friend Code Directory** — Searchable, platform-aware player directory
6. **Match Analytics** — Shot time tracking, slow play detection, cheat pattern flagging

**Why Ripstone should care:**
- Their #1 support burden is online/multiplayer issues — a matchmaking bot reduces tickets
- ONE person handles ALL bug reports — a structured tracker would 10x their throughput
- Bug reproduction is their #1 bottleneck — structured reproduction steps from players = gold
- POTM is their best engagement driver — tournaments systematize it
- They're asking for Steam reviews (186/200 goal) — community tools drive retention → reviews
- Patch 3 added Ranked mode — leaderboards make rankings visible and sticky
- Slow play is a community complaint — analytics could flag chronic stallers
- Xbox launch coming — cross-platform friend matching reduces platform friction
- Snooker DLC in development — bot can support new mode from day one
- They have no community tools beyond a basic Discord link

**Why you:**
- You've already built tournament management (Challonge API, 432 messages)
- You have a working Discord bot (cuebot) with match management
- You understand the pool/billiards community (you play)
- You're already in their ecosystem (Discord server member)
- You can demo on YOUR server before pitching theirs
