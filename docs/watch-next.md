# Reading Continue watching

A launcher can show the rows other apps publish to the system's Continue watching (Watch Next)
and preview channels. They live in the TV provider, behind `TvContract.WatchNextPrograms` and
`TvContract.PreviewPrograms`.

- **Permission:** `android.permission.READ_TV_LISTINGS`, a runtime permission. Request it with
  the normal dialog, or grant it from a shell: `pm grant <package> android.permission.READ_TV_LISTINGS`.
- **Not needed:** `com.android.providers.tv.permission.ACCESS_ALL_EPG_DATA` is
  `signature|privileged`, so a sideloaded app cannot hold it. With only `READ_TV_LISTINGS` a query returns
  the caller's own rows plus every row marked `searchable`.
- **Query without a selection:** a caller without `ACCESS_ALL_EPG_DATA` gets a `SecurityException`
  when it passes one. Read the whole table and filter in code.
- **Some apps publish nothing.** Rows exist only if the app writes them and marks them
  searchable, and some apps do neither, so query on the target TV before relying on an app.
  Query from an app that holds `READ_TV_LISTINGS`, not from the shell: the shell lacks it, so
  `content query --uri content://android.media.tv/watch_next_program` (or `channel`,
  `preview_program`) prints `No result found.` and cannot tell whether any app publishes rows.
- **Seen on a Chromecast with Google TV 4K** (Google TV 14, `UTTC.250917.004`): a test build
  holding `READ_TV_LISTINGS` and querying without a selection saw 6 channels and 51 preview
  programs, all from YouTube and Spotify, and no Watch Next rows. Poster URIs were `https://` (one
  Spotify poster aside, `android.resource://`), so a reader needs network access to show most of
  them; `intent_uri` held `intent:` URIs. Plex (`com.plexapp.android` 2026.20.0, which requests
  `WRITE_EPG_DATA`) had no channel, preview or Watch Next rows visible. Without
  `ACCESS_ALL_EPG_DATA` a reader sees only its own rows plus rows marked `searchable`, so Plex rows
  that are not searchable would be invisible too: the probe cannot tell "publishes nothing" from
  "publishes only non-searchable rows".

Source: `createSqlParams()` in `packages/providers/TvProvider/src/com/android/providers/tv/TvProvider.java`
(AOSP) holds the `READ_TV_LISTINGS` and `searchable` logic; both permissions are defined in that
module's `AndroidManifest.xml`.

## Temporary CleanYourTV UI diagnostic (Phase 1 only)

The UI launcher (`io.cleanyourtv.ui`, Android 9 / API 28 minimum, target 33) now has an explicit,
read-only diagnostic. It does not add a Home row, change the layout, resume anything, fetch artwork,
call TMDB, or run automatically. The normal Home screen does not query TvProvider.

`TvProviderDiagnosticActivity` dispatches the work to a background thread and finishes when it is
done. It requires the **caller's** `android.permission.DUMP`, normally held by the ADB shell but not
ordinary apps. The launcher does not request that permission itself. There is no menu or intent
filter for the diagnostic. If a manufacturer refuses the shell entry point, report that failure;
do not remove the protection or root the TV.

### Build, install and run

Build from this repository using [the UI build instructions](../README.md). The resulting APK is
`launcher-ui/CleanYourTV-UI.apk`; keep the existing local signing key for an update. The following
commands assume native `adb` is installed, the TV has already authorized this computer, and the
updated APK is installed. Replace `<tv ip>` with the TV's address.

```powershell
$env:TV_HOST='<tv ip>'
adb connect "$($env:TV_HOST):5555"
adb install -r launcher-ui\CleanYourTV-UI.apk
adb shell pm grant io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
```

In one terminal, start capturing **before** launching the diagnostic (leave other log buffers alone):

```sh
adb logcat -v threadtime -s CYTV-TvProvider:I "*:S"
```

In another terminal:

```sh
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity
```

That first run shows titles, packages, metadata and progress, but redacts URI/intent/internal-provider
columns and other recognizable sensitive columns. It is **not guaranteed safe to publish**: arbitrary
vendor columns, titles and error messages can still be personal or sensitive.

For the requested **full raw inspection**, explicitly opt in:

```sh
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity --ez raw_values true
```

**Keep raw logs local.** They contain viewing history; URLs, intent extras and opaque provider data
may include account identifiers or access tokens. Do not upload the output or commit it. Redact it
before sharing even a short excerpt. The diagnostic does not write its own files or transmit data.
Logcat retains entries until they roll out of its buffers; revoking the permission does not erase logs.

Without native `adb`, the existing Python tools can transfer the APK and run the same device-side
commands from the repository root. Use this alternative instead of the native installation above:

```powershell
$env:TV_HOST='<tv ip>'
& tools\venv\Scripts\python.exe -I tools\b64push.py launcher-ui\CleanYourTV-UI.apk /data/local/tmp/cleanyourtv-ui.apk
& tools\venv\Scripts\python.exe -I tools\tv.py 'pm install -r /data/local/tmp/cleanyourtv-ui.apk'
```

Continue only if the transfer verifies and the installation reports `Success`. An update must use
the existing signing key; stop on an install failure rather than uninstalling the working launcher.
Then grant, trigger and read the retained logs:

```powershell
$env:TV_HOST='<tv ip>'
& tools\venv\Scripts\python.exe -I tools\tv.py 'pm grant io.cleanyourtv.ui android.permission.READ_TV_LISTINGS'
& tools\venv\Scripts\python.exe -I tools\tv.py 'am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity --ez raw_values true'
& tools\venv\Scripts\python.exe -I tools\tv.py 'logcat -d -v threadtime -s CYTV-TvProvider:I "*:S"'
```

The last command dumps retained log entries instead of keeping a streaming connection open. Run it
again if the matching `END` has not appeared yet. Use the `run=` identifier to distinguish runs.
No TV install occurs just by building, and this update does not change the default Home selection
or debloat settings.

### What the output means

Every run lists visible enabled Leanback app packages (not a guarantee that they publish anything),
the runtime/privileged permission states, and independent results for:

- `WATCH_NEXT`: the system's Watch Next records.
- `PREVIEW_PROGRAM`: preview-channel records, which can be recommendations rather than resume items.
- `CHANNEL`: publisher/channel metadata; use `_id` to interpret preview `channel_id`.

Each query uses a null projection, selection and sort order. Every accessible row and every returned
column is logged, including unknown/vendor fields, with its cursor type and original value. No package
filter, deduplication, inferred metadata, fabricated progress, or row limit is applied. Column types are
`0=null`, `1=integer`, `2=float`, `3=string`, `4=blob`. Missing columns appear only by their absence from
the schema; nulls stay null and zero stays zero. Binary values are base64 only in raw mode.

Look for `_id`, `package_name`, `title`, `short_description`, `long_description`, `type`,
`watch_next_type`, `season_display_number`, `episode_display_number`, `episode_title`,
`last_playback_position_millis`, `duration_millis`, `last_engagement_time_utc_millis`,
`poster_art_uri`, `thumbnail_uri`, `preview_video_uri`, `intent_uri`, `searchable`, `browsable`,
`content_id`, `internal_provider_id` and any provider-specific identifiers. Availability varies;
the diagnostic does not request a fixed column list that would fail on an older schema.

For example (illustrative, not results from your TV):

```text
run=123 READ_TV_LISTINGS=GRANTED ACCESS_ALL_EPG_DATA=DENIED
run=123 WATCH_NEXT row=1 column="_id" type=1 value= 42
run=123 WATCH_NEXT row=1 column="package_name" type=3 value= "com.example.player"
run=123 WATCH_NEXT row=1 column="title" type=3 value= "Example show"
run=123 WATCH_NEXT row=1 column="last_playback_position_millis" type=1 value= 1200000
run=123 WATCH_NEXT row=1 column="duration_millis" type=1 value= 2400000
run=123 WATCH_NEXT PUBLISHER rows=1 package= "com.example.player"
run=123 WATCH_NEXT END status=OK rows_visited=1 field_errors=0 complete=true
run=123 PREVIEW_PROGRAM END status=OK rows_visited=0 field_errors=0 complete=true
run=123 CHANNEL END status=OK rows_visited=0 field_errors=0 complete=true
run=123 END status=COMPLETE complete_sources=3/3 inventory_ok=true
```

Long values are split into numbered character ranges, preserving surrogate pairs and repeating the
source/row/column prefix, rather than silently truncating a URI at logcat's per-entry byte limit.
Strings use JSON quoting so embedded line breaks cannot impersonate other diagnostic records.
Writes are briefly paced because older TVs can drop rapid log bursts even during live capture.
Large channel tables can take a minute or longer; wait for the final run-level `END`. Keep a live
capture running before triggering the probe, since a large dump can exceed logcat's retained buffer.

- `OK` with zero rows means **no rows accessible to this launcher**, not proof that nothing is published.
- `SECURITY_EXCEPTION` identifies a denied table. Verify the runtime grant first. A granted permission
  does not guarantee that a manufacturer's provider exposes other apps' records.
- `UNSUPPORTED` / `UNAVAILABLE_OR_INVALID_QUERY` identifies an unsupported table or rejected query.
- `NULL_CURSOR` is a failed/inconclusive query, never represented as an empty success.
- `QUERY_OR_CURSOR_ERROR` or `FIELD_ERRORS` means incomplete data; earlier rows may still be useful.
- Each failure includes its exception type, message and stack trace. Other tables are still attempted.
- A completed run with any failure says `COMPLETED_WITH_ERRORS`. A missing final `END` is incomplete:
  inspect logcat for process/provider crashes or a stalled query; do not interpret it as zero records.
- `ACCESS_ALL_EPG_DATA=DENIED` is expected for this sideloaded launcher. Do not try to grant privileged
  permissions, add write permissions, or use shell `content query` as a substitute for this app probe.

To deliberately verify denial reporting, revoke the read permission and then launch the diagnostic
again (revoking may restart the launcher process):

```sh
adb shell pm revoke io.cleanyourtv.ui android.permission.READ_TV_LISTINGS
adb shell am start -n io.cleanyourtv.ui/.TvProviderDiagnosticActivity
```

Restore the grant before collecting real coverage results. After testing, it can be revoked again.
To remove the facility, delete `TvProviderDiagnostic.java`, `TvProviderDiagnosticActivity.java`, its
manifest activity entry and the added `READ_TV_LISTINGS` permission, and remove this documentation
section and its diagnostic tests. No Home code or persisted launcher preferences need reverting.

Stop here and evaluate the TV's actual results before adding a normalized source, repository, row,
resume action, TMDB enrichment or search integration.
