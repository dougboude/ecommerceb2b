# Cross-Page Feedback Contract Matrix

This matrix defines consistent feedback and recovery behavior for Feature 2
(`cross-page-feedback-recovery-empty-state-system`).

## Mutating Actions

| Action | Success feedback | Recovery/next step |
|---|---|---|
| Create demand listing | `Demand listing created.` | Redirect to demand detail |
| Update demand listing | `Demand listing updated.` | Redirect to demand detail |
| Pause demand listing | `Demand listing paused.` | Redirect to demand detail |
| Resume demand listing | `Demand listing resumed.` | Redirect to demand detail |
| Delete demand listing | `Demand listing deleted.` | Redirect to demand list |
| Create supply listing | `Supply listing created.` | Redirect to supply detail |
| Update supply listing | `Supply listing updated.` | Redirect to supply detail |
| Withdraw supply listing | `Supply listing withdrawn.` | Redirect to supply detail |
| Reactivate supply listing | `Supply listing reactivated.` | Redirect to supply detail |
| Delete supply listing | `Supply listing deleted.` | Redirect to supply list |
| Discover save | `Saved to watchlist.` | Return to discover results |
| Discover unsave | `Removed from watchlist.` | Return to discover results |
| Discover message | `Conversation ready. Send your message below.` | Redirect to thread detail |
| Suggestion save | `Saved to watchlist.` | Redirect to provided `next` |
| Suggestion dismiss | `Suggestion dismissed. You can find more matches in Discover.` | Redirect to provided `next` |
| Suggestion message | `Conversation ready. Send your message below.` | Redirect to thread detail |
| Watchlist star | `Added to starred items.` | Redirect to watchlist (non-HTMX) |
| Watchlist unstar | `Moved to watching.` | Redirect to watchlist (non-HTMX) |
| Watchlist archive | `Watchlist item archived.` | Redirect to watchlist |
| Watchlist unarchive | `Watchlist item restored to watching.` | Redirect to watchlist |
| Watchlist remove | `Removed from watchlist.` | Redirect to watchlist |
| Profile update | `Profile updated.` | Redirect to profile |
| Verify email confirm | `Email verified. Welcome to NicheMarket!` | Redirect to dashboard |
| Discover clear | `Search cleared. Try a new query.` | Redirect to discover |

## Empty-State CTA Contract

| Surface | Empty-state primary CTA |
|---|---|
| Inbox | `Discover listings` |
| Watchlist | `Discover more` |
| Discover no results | `Start a new search` |
| Supply list | `Create new` |
| Demand list | `Create new` |
| Profile supply section | `Create supply listing` |
| Profile demand section | `Create demand listing` |

## Confirmation Contract

| Action | Confirm mechanism | Safe cancel path |
|---|---|---|
| Listing delete (supply/demand) | Dedicated confirmation page with explicit `Yes, delete` | `Cancel` returns to listing detail |
| Watchlist remove | Browser confirm dialog on submit | Cancel leaves card unchanged |
