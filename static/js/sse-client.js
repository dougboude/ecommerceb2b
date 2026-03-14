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
    var rowFetchInFlight = {};

    function updateInboxPage(data) {
        if (!document.getElementById("sse-inbox-page")) return;

        var workspace = document.querySelector(".messages-workspace");
        if (!workspace) return;

        var mode = (workspace.getAttribute("data-view-mode") || "flat").toLowerCase();
        var row = document.querySelector('[data-thread-id="' + data.thread_id + '"]');
        if (row) {
            updateInboxRow(row, data);
            moveRowToTop(row, mode, data.listing_id);
            return;
        }

        // Missing row path: fetch canonical server-rendered row fragment.
        var threadKey = String(data.thread_id);
        if (rowFetchInFlight[threadKey]) return;
        rowFetchInFlight[threadKey] = true;
        fetchInboxRowFragment(data.thread_id)
            .then(function (fetchedRow) {
                if (!fetchedRow) return;
                removeInboxEmptyState();
                insertInboxRow(fetchedRow, mode, data.listing_id, data.listing_title);
                updateInboxRow(fetchedRow, data);
                moveRowToTop(fetchedRow, mode, data.listing_id);
                if (window.htmx) window.htmx.process(fetchedRow);
            })
            .catch(function () {})
            .finally(function () {
                delete rowFetchInFlight[threadKey];
            });
    }

    function fetchInboxRowFragment(threadId) {
        var url = "/messages/row/" + encodeURIComponent(threadId) + "/fragment/";
        return fetch(url, {
            credentials: "same-origin",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .then(function (resp) {
                if (!resp.ok) return null;
                return resp.text();
            })
            .then(function (html) {
                if (!html) return null;
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, "text/html");
                return doc.querySelector('[data-thread-id]');
            });
    }

    function updateInboxRow(row, data) {
        if (!row.classList.contains("thread-unread")) {
            row.classList.add("thread-unread");
        }

        var preview = row.querySelector(".thread-preview");
        if (preview) {
            preview.textContent = data.message_preview || data.message_body || "";
        }

        var badgeContainer = row.querySelector("[data-badge-container]");
        if (badgeContainer && !badgeContainer.querySelector(".nav-badge")) {
            var badge = document.createElement("span");
            badge.className = "nav-badge";
            badge.textContent = "New";
            badgeContainer.insertBefore(badge, badgeContainer.firstChild);
        }
    }

    function insertInboxRow(row, mode, listingId, listingTitle) {
        if (mode === "grouped") {
            var groupRows = ensureListingGroupRows(listingId, listingTitle);
            if (groupRows) {
                groupRows.insertBefore(row, groupRows.firstChild);
                return;
            }
        }
        var container = document.getElementById("messages-list-rows");
        if (!container) return;
        container.insertBefore(row, container.firstChild);
    }

    function moveRowToTop(row, mode, listingId) {
        if (mode === "grouped") {
            var groupRows = listingId ? ensureListingGroupRows(listingId) : null;
            if (groupRows && groupRows.firstElementChild !== row) {
                groupRows.insertBefore(row, groupRows.firstElementChild);
            }
            var group = groupRows ? groupRows.closest("[data-listing-group-id]") : null;
            var groupsRoot = document.getElementById("messages-list-groups");
            if (group && groupsRoot && groupsRoot.firstElementChild !== group) {
                groupsRoot.insertBefore(group, groupsRoot.firstElementChild);
            }
            return;
        }
        var parent = row.parentNode;
        if (parent && parent.firstElementChild !== row) {
            parent.insertBefore(row, parent.firstElementChild);
        }
    }

    function removeInboxEmptyState() {
        var empty = document.getElementById("messages-list-empty-state");
        if (empty) {
            empty.hidden = true;
        }
    }

    function ensureListingGroupRows(listingId, listingTitle) {
        if (!listingId) return null;
        var groupsRoot = document.getElementById("messages-list-groups");
        if (!groupsRoot) {
            groupsRoot = document.createElement("div");
            groupsRoot.id = "messages-list-groups";
            groupsRoot.className = "messages-list-groups";
            var listPane = document.querySelector(".messages-list-pane");
            if (!listPane) return null;
            var flatRows = document.getElementById("messages-list-rows");
            if (flatRows) flatRows.hidden = true;
            listPane.appendChild(groupsRoot);
        }
        var selector = '[data-listing-group-id="' + listingId + '"]';
        var group = groupsRoot.querySelector(selector);
        if (!group) {
            group = document.createElement("section");
            group.className = "messages-list-group";
            group.setAttribute("data-listing-group-id", String(listingId));

            var heading = document.createElement("h3");
            heading.className = "messages-list-group-title";
            heading.textContent = listingTitle || "Listing";
            group.appendChild(heading);

            var rows = document.createElement("div");
            rows.className = "messages-list-group-rows";
            group.appendChild(rows);
            groupsRoot.insertBefore(group, groupsRoot.firstElementChild);
        }
        return group.querySelector(".messages-list-group-rows");
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
