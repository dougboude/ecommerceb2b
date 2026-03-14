/**
 * SSE client — connects to the SSE sidecar and handles real-time updates.
 *
 * Handles four page contexts:
 * 1. Navbar badge (any page) — updates unread count
 * 2. Thread detail — inserts new received messages by timestamp
 * 3. Inbox — marks threads as unread, updates preview
 * 4. Watchlist — updates per-thread unread count on the card badge
 */
function initSSE(streamUrl) {
    "use strict";

    var MAX_RETRIES = 10;
    var retryCount = 0;
    var source = null;

    function connect() {
        source = new EventSource(streamUrl);

        source.onopen = function () {
            retryCount = 0;
        };

        source.addEventListener("new_message", function (e) {
            var data;
            try {
                data = JSON.parse(e.data);
            } catch (_) {
                return;
            }
            var currentThreadId = getCurrentThreadId();
            var isCurrentThread = currentThreadId !== null && data.thread_id === currentThreadId;
            if (isCurrentThread) {
                // Don't show "new" for the thread already in view.
                updateNavBadge(Math.max((data.unread_count || 0) - 1, 0));
            } else {
                updateNavBadge(data.unread_count);
            }
            updateThreadPage(data);
            updateInboxPage(data);
            updateWatchlistPage(data);
        });

        source.addEventListener("listing_updated", function (e) {
            var data;
            try {
                data = JSON.parse(e.data);
            } catch (_) {
                return;
            }
            refreshWatchlistPage(data);
        });

        source.onerror = function () {
            source.close();
            retryCount++;
            if (retryCount <= MAX_RETRIES) {
                var delay = Math.min(1000 * Math.pow(2, retryCount - 1), 30000);
                setTimeout(connect, delay);
            }
        };
    }

    function getCurrentThreadId() {
        var container = document.getElementById("sse-messages-list");
        if (!container) return null;
        var threadId = parseInt(container.getAttribute("data-thread-id"), 10);
        return Number.isFinite(threadId) ? threadId : null;
    }

    // --- Navbar badge ---
    function updateNavBadge(unreadCount) {
        var link = document.getElementById("nav-messages-link");
        if (!link) return;

        var badge = document.getElementById("nav-unread-badge");

        if (unreadCount > 0) {
            if (badge) {
                badge.textContent = unreadCount;
            } else {
                badge = document.createElement("span");
                badge.className = "nav-badge";
                badge.id = "nav-unread-badge";
                badge.textContent = unreadCount;
                link.appendChild(badge);
            }
        } else if (badge) {
            badge.remove();
        }
    }

    // --- Thread detail page ---
    function updateThreadPage(data) {
        var container = document.getElementById("sse-messages-list");
        if (!container) return;

        var threadId = parseInt(container.getAttribute("data-thread-id"), 10);
        if (data.thread_id !== threadId) return;

        // Build new message element
        var div = document.createElement("div");
        div.className = "message received";
        var messageTs = asUnixTs(data.message_created_at);
        div.dataset.messageTs = String(messageTs);

        var strong = document.createElement("strong");
        strong.textContent = data.sender_name;

        var span = document.createElement("span");
        var dt = new Date(data.message_created_at);
        span.textContent = dt.toLocaleString();

        var p = document.createElement("p");
        p.textContent = data.message_body;

        div.appendChild(strong);
        div.appendChild(span);
        div.appendChild(p);

        // Insert before the empty-state or at end of list
        var emptyState = container.querySelector(".empty-state");
        if (emptyState) emptyState.remove();

        insertMessageByTimestamp(container, div);
        div.scrollIntoView({ behavior: "smooth", block: "end" });
    }

    function asUnixTs(isoString) {
        var parsed = Date.parse(isoString);
        if (!Number.isFinite(parsed)) return 0;
        return Math.floor(parsed / 1000);
    }

    function insertMessageByTimestamp(container, messageNode) {
        var existingMessages = Array.from(container.querySelectorAll(".message"));
        var newTs = Number(messageNode.dataset.messageTs || 0);
        var inserted = false;

        for (var i = 0; i < existingMessages.length; i++) {
            var existingTs = Number(existingMessages[i].dataset.messageTs || 0);
            if (newTs < existingTs) {
                container.insertBefore(messageNode, existingMessages[i]);
                inserted = true;
                break;
            }
        }

        if (!inserted) {
            container.appendChild(messageNode);
        }
    }

    // --- Inbox page ---
    function updateInboxPage(data) {
        if (!document.getElementById("sse-inbox-page")) return;

        var row = document.querySelector(
            '[data-thread-id="' + data.thread_id + '"]'
        );
        if (!row) return;

        // Mark as unread
        if (!row.classList.contains("thread-unread")) {
            row.classList.add("thread-unread");
        }

        // Update preview text
        var preview = row.querySelector(".thread-preview");
        if (preview) {
            var text = data.message_body;
            if (text.length > 80) text = text.substring(0, 80) + "...";
            preview.textContent = text;
        }

        // Add "New" badge if not present
        var badgeContainer = row.querySelector("[data-badge-container]");
        if (badgeContainer && !badgeContainer.querySelector(".nav-badge")) {
            var badge = document.createElement("span");
            badge.className = "nav-badge";
            badge.textContent = "New";
            badgeContainer.insertBefore(badge, badgeContainer.firstChild);
        }

        // Move thread to top of list
        var parent = row.parentNode;
        if (parent && parent.firstElementChild !== row) {
            parent.insertBefore(row, parent.firstElementChild);
        }
    }

    // --- Watchlist page ---
    function updateWatchlistPage(data) {
        if (!document.getElementById("sse-watchlist-page")) return;

        var badge = document.getElementById("watchlist-badge-" + data.thread_id);
        if (!badge) return;

        var count = data.thread_unread_count || 0;
        var unreadSpan = badge.querySelector(".watchlist-unread-count");

        if (count > 0) {
            if (unreadSpan) {
                unreadSpan.textContent = " \u00b7 " + count + " unread";
            } else {
                unreadSpan = document.createElement("span");
                unreadSpan.className = "watchlist-unread-count";
                unreadSpan.textContent = " \u00b7 " + count + " unread";
                badge.appendChild(unreadSpan);
            }
        }
    }

    var watchlistRefreshInFlight = false;
    var watchlistRefreshQueued = false;

    function refreshWatchlistPage(_data) {
        if (!document.getElementById("sse-watchlist-page")) return;
        if (watchlistRefreshInFlight) {
            watchlistRefreshQueued = true;
            return;
        }

        var existingContent = document.getElementById("watchlist-content");
        if (!existingContent) return;
        var archivedDetails = existingContent.querySelector(".watchlist-archived");
        var archivedOpen = !!(archivedDetails && archivedDetails.open);

        watchlistRefreshInFlight = true;
        var url = window.location.pathname + window.location.search;
        fetch(url, {
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
        })
            .then(function (resp) { return resp.text(); })
            .then(function (html) {
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, "text/html");
                var nextContent = doc.getElementById("watchlist-content");
                var currentContent = document.getElementById("watchlist-content");
                if (!nextContent || !currentContent) return;

                currentContent.replaceWith(nextContent);
                if (archivedOpen) {
                    var newArchived = document.querySelector("#watchlist-content .watchlist-archived");
                    if (newArchived) newArchived.open = true;
                }
            })
            .catch(function () {})
            .finally(function () {
                watchlistRefreshInFlight = false;
                if (watchlistRefreshQueued) {
                    watchlistRefreshQueued = false;
                    refreshWatchlistPage();
                }
            });
    }

    connect();
}
