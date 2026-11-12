# Email Bot Roadmap (Updated)

## Goal

Build a simple dashboard to send **50 to 100 emails per day** safely.

Stack

-   FastAPI
-   HTMX
-   Bootstrap
-   SQLite
-   Jinja2
-   SMTP

------------------------------------------------------------------------

# Email Sending Logic

The sender should behave like a real person instead of sending emails
back to back.

Workflow

``` text
Start Campaign

↓

Load SMTP

↓

Load Email Template

↓

Load CSV

↓

Select First Unsent Contact

↓

Replace Variables

↓

Send Email

↓

Save Status

↓

Wait Random Time (4 to 15 minutes)

↓

Next Contact
```

## Random Delay

Every email waits a random amount of time.

Example

-   Email 1
    -   Wait 6 minutes
-   Email 2
    -   Wait 13 minutes
-   Email 3
    -   Wait 4 minutes
-   Email 4
    -   Wait 11 minutes

Never use a fixed interval.

------------------------------------------------------------------------

## Campaign Rules

-   Send only one email at a time.
-   Pick a random delay between 4 and 15 minutes after every successful
    send.
-   Retry a failed email once after a longer random wait.
-   Save progress after every send.
-   Resume from the last unsent contact after a restart.
-   Stop immediately if the daily limit is reached.

------------------------------------------------------------------------

## Daily Limit

Default: 50 emails

Optional: 100 emails

Once the limit is reached:

-   Pause automatically
-   Resume the next day

------------------------------------------------------------------------

## Status Tracking

Each recipient stores:

-   Email
-   Name
-   Campaign
-   Status
-   Sent Time
-   Retry Count
-   Error Message

Status values

-   Pending
-   Sending
-   Sent
-   Failed
-   Retry
-   Skipped

------------------------------------------------------------------------

## Dashboard

Home

-   Emails sent today
-   Remaining today
-   Active campaign
-   Queue size
-   Success rate

Campaign

-   Start
-   Pause
-   Resume
-   Stop

Logs

-   Successful sends
-   Failed sends
-   Retry history

------------------------------------------------------------------------

## Safety

-   Random delay for every email
-   One SMTP connection per send
-   Validate email before sending
-   Skip duplicates
-   Respect provider daily limits
-   Never send two emails at the same moment

------------------------------------------------------------------------

## Future Features

-   Multiple SMTP accounts
-   SMTP rotation
-   Scheduling
-   Multiple campaigns
-   HTML editor
-   Attachment support
-   Bounce detection
-   Amazon SES
-   SendGrid
-   Mailgun
-   Analytics
