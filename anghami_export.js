/*
 * Anghami Export Script (Browser Console) — Step-by-Step
 * =======================================================
 *
 * INSTRUCTIONS:
 *   1. Open https://play.anghami.com in Chrome/Edge and LOG IN
 *   2. Press F12 → Console tab
 *   3. Paste this ENTIRE script and press Enter
 *      → It creates helper commands you can call
 *
 *   4. Navigate to your LIKED SONGS page in Anghami (click it in the sidebar)
 *      → Scroll ALL the way down to load everything
 *      → Then type in the console:   grabSongs("liked")
 *
 *   5. Navigate to EACH PLAYLIST you want to export
 *      → Scroll ALL the way down to load everything
 *      → Then type:   grabSongs("My Playlist Name")
 *      → Repeat for each playlist
 *
 *   6. When you're done with all playlists, type:   downloadExport()
 *      → This downloads "anghami_export.json"
 *      → Run:  python main.py --from-json anghami_export.json
 *
 *   TIP: Type  showStatus()  anytime to see what you've collected so far.
 */

// ── Storage ──
if (!window._anghamiExport) {
    window._anghamiExport = { liked_songs: [], playlists: [] };
}

// ── Extract songs visible on the current page ──
function _extractSongs() {
    let songs = [];
    let seen = new Set();

    // Strategy 1: Find all links pointing to /song/ paths
    document.querySelectorAll('a[href*="/song/"]').forEach(a => {
        let href = a.getAttribute('href');
        if (seen.has(href)) return;
        seen.add(href);

        let title = a.textContent.trim();
        if (!title || title.length > 200) return;

        let artist = 'Unknown Artist';
        // Walk up to find the row/container, then look for artist text
        let row = a.closest(
            '[class*="song"], [class*="Song"], [class*="track"], [class*="Track"], ' +
            '[class*="row"], [class*="Row"], [class*="item"], [class*="Item"], ' +
            'tr, li, [class*="cell"], [class*="list"]'
        );
        if (row) {
            let artistEl = row.querySelector(
                '[class*="artist"], [class*="Artist"], [class*="subtitle"], ' +
                '[class*="Subtitle"], [class*="secondary"], [class*="sub"]'
            );
            if (artistEl) {
                let t = artistEl.textContent.trim();
                if (t && t !== title) artist = t;
            }
        }
        songs.push({ title, artist });
    });

    // Strategy 2: Structured containers (fallback)
    if (songs.length === 0) {
        document.querySelectorAll(
            '[class*="song"], [class*="Song"], [class*="track"], [class*="Track"]'
        ).forEach(el => {
            let titleEl = el.querySelector(
                '[class*="title"], [class*="Title"], [class*="name"], [class*="Name"]'
            );
            let artistEl = el.querySelector(
                '[class*="artist"], [class*="Artist"], [class*="subtitle"], [class*="Subtitle"]'
            );
            if (titleEl && titleEl.textContent.trim()) {
                let title = titleEl.textContent.trim();
                let artist = artistEl ? artistEl.textContent.trim() : 'Unknown Artist';
                let key = title + '|' + artist;
                if (!seen.has(key)) {
                    seen.add(key);
                    songs.push({ title, artist });
                }
            }
        });
    }

    // Strategy 3: Look for any repeated list structure with text
    if (songs.length === 0) {
        // Get all elements that look like list items with meaningful text
        let candidates = document.querySelectorAll('li, [role="listitem"], [role="row"]');
        candidates.forEach(el => {
            let links = el.querySelectorAll('a');
            let texts = [];
            links.forEach(a => {
                let t = a.textContent.trim();
                if (t && t.length > 1 && t.length < 200) texts.push(t);
            });
            if (texts.length >= 1) {
                let title = texts[0];
                let artist = texts.length >= 2 ? texts[1] : 'Unknown Artist';
                let key = title + '|' + artist;
                if (!seen.has(key)) {
                    seen.add(key);
                    songs.push({ title, artist });
                }
            }
        });
    }

    return songs;
}

// ── Grab songs from the current page ──
window.grabSongs = function(label) {
    let songs = _extractSongs();
    if (songs.length === 0) {
        console.warn('⚠️  No songs found on this page!');
        console.log('Make sure you:');
        console.log('  1. Are on a page that shows a list of songs');
        console.log('  2. Scrolled ALL the way down to load everything');
        console.log('  3. Try running:  inspectPage()  to see what the script can detect');
        return;
    }

    if (label === 'liked' || label === 'likes' || label === 'favorites') {
        window._anghamiExport.liked_songs = songs;
        console.log(`✅ Saved ${songs.length} LIKED songs`);
    } else {
        // Check if playlist already exists, update it
        let existing = window._anghamiExport.playlists.findIndex(p => p.name === label);
        if (existing >= 0) {
            window._anghamiExport.playlists[existing].songs = songs;
            console.log(`✅ Updated playlist "${label}" — ${songs.length} songs`);
        } else {
            window._anghamiExport.playlists.push({ name: label, songs });
            console.log(`✅ Added playlist "${label}" — ${songs.length} songs`);
        }
    }
    showStatus();
};

// ── Show current status ──
window.showStatus = function() {
    let e = window._anghamiExport;
    console.log('\n📊 Current export status:');
    console.log(`   Liked songs: ${e.liked_songs.length}`);
    console.log(`   Playlists: ${e.playlists.length}`);
    e.playlists.forEach(p => {
        console.log(`     • "${p.name}" — ${p.songs.length} songs`);
    });
    console.log('');
};

// ── Debug: inspect what the script can see on the page ──
window.inspectPage = function() {
    console.log('\n🔍 Page inspection:');
    console.log('   URL:', window.location.href);

    let songLinks = document.querySelectorAll('a[href*="/song/"]');
    console.log(`   Links with /song/: ${songLinks.length}`);
    if (songLinks.length > 0) {
        console.log('   First 3:');
        Array.from(songLinks).slice(0, 3).forEach(a => {
            console.log('     ', a.textContent.trim().substring(0, 60), '→', a.href);
        });
    }

    let playlistLinks = document.querySelectorAll('a[href*="/playlist/"]');
    console.log(`   Links with /playlist/: ${playlistLinks.length}`);
    if (playlistLinks.length > 0) {
        console.log('   Playlists found:');
        let seen = new Set();
        playlistLinks.forEach(a => {
            let href = a.getAttribute('href');
            if (!seen.has(href)) {
                seen.add(href);
                console.log('     ', a.textContent.trim().substring(0, 60), '→', href);
            }
        });
    }

    // Show all link patterns on the page
    let patterns = {};
    document.querySelectorAll('a[href]').forEach(a => {
        let href = a.getAttribute('href');
        let match = href.match(/^\/([^/]+)\//);
        if (match) {
            patterns[match[1]] = (patterns[match[1]] || 0) + 1;
        }
    });
    console.log('   Link patterns:', patterns);
    console.log('');
};

// ── Download the final export ──
window.downloadExport = function() {
    let e = window._anghamiExport;
    let total = e.liked_songs.length;
    e.playlists.forEach(p => total += p.songs.length);

    if (total === 0) {
        console.error('❌ Nothing to export! Use grabSongs() first.');
        return;
    }

    let json = JSON.stringify(e, null, 2);
    let blob = new Blob([json], { type: 'application/json' });
    let url = URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = 'anghami_export.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log(`\n✅ Downloaded anghami_export.json`);
    console.log(`   ${e.liked_songs.length} liked songs, ${e.playlists.length} playlists, ${total} total songs`);
    console.log(`\n   Next: python main.py --from-json anghami_export.json`);
};

// ── Ready message ──
console.log('');
console.log('🎵 Anghami Export Tool Ready!');
console.log('============================');
console.log('');
console.log('Commands:');
console.log('  grabSongs("liked")           — Save liked songs from current page');
console.log('  grabSongs("Playlist Name")   — Save a playlist from current page');
console.log('  showStatus()                 — See what you\'ve collected');
console.log('  inspectPage()                — Debug: see what the script detects');
console.log('  downloadExport()             — Download the final JSON file');
console.log('');
console.log('Steps:');
console.log('  1. Navigate to your liked songs → scroll down → grabSongs("liked")');
console.log('  2. Navigate to each playlist → scroll down → grabSongs("name")');
console.log('  3. downloadExport()');
console.log('');
