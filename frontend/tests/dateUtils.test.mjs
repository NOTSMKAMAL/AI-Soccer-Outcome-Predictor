// Run with `npm test`. Uses Node's built-in test runner, so it adds no dependency.
import assert from "node:assert/strict";
import { after, describe, it } from "node:test";

import {
  formatDailyReset,
  formatLocalDateLabel,
  formatLocalDateLong,
  formatLocalTime,
  isUpcomingLocal,
  nextDailyReset,
  parseFixtureDate,
  todayLocal,
  toLocalDateStr,
  tomorrowLocal,
} from "../src/lib/dateUtils.ts";

const LOS_ANGELES = "America/Los_Angeles";
const LONDON = "Europe/London";
const NEW_YORK = "America/New_York";
const TOKYO = "Asia/Tokyo";

const at = (iso) => new Date(iso);
// Newer ICU versions put a narrow no-break space before AM/PM.
const plain = (text) => text.replace(/ /g, " ");

describe("the viewer's day", () => {
  it("is the same instant on different calendar days around the world", () => {
    const kickoff = at("2026-11-01T02:00:00Z");
    assert.equal(toLocalDateStr(kickoff, LOS_ANGELES), "2026-10-31");
    assert.equal(toLocalDateStr(kickoff, LONDON), "2026-11-01");
    assert.equal(toLocalDateStr(kickoff, TOKYO), "2026-11-01");
  });

  it("rolls tomorrow over a month and a year", () => {
    assert.equal(tomorrowLocal("UTC", at("2026-10-31T12:00:00Z")), "2026-11-01");
    assert.equal(tomorrowLocal("UTC", at("2026-12-31T12:00:00Z")), "2027-01-01");
  });

  it("handles a leap day", () => {
    assert.equal(tomorrowLocal("UTC", at("2028-02-28T12:00:00Z")), "2028-02-29");
  });

  it("does not skip a day when the clocks change", () => {
    assert.equal(tomorrowLocal(LOS_ANGELES, at("2026-11-01T20:00:00Z")), "2026-11-02");
    assert.equal(tomorrowLocal(LOS_ANGELES, at("2026-03-08T20:00:00Z")), "2026-03-09");
  });

  it("reports an invalid date instead of a wrong day", () => {
    assert.equal(toLocalDateStr(at("not a date"), TOKYO), "invalid");
  });
});

describe("Today and Tomorrow labels", () => {
  const now = at("2026-10-31T20:00:00Z");
  const kickoff = at("2026-11-01T02:00:00Z");

  it("are today in Los Angeles", () => {
    assert.equal(formatLocalDateLabel(kickoff, LOS_ANGELES, now), "TODAY");
  });

  it("are tomorrow in London for the same match", () => {
    assert.equal(formatLocalDateLabel(kickoff, LONDON, now), "TOMORROW");
  });

  it("are today in Tokyo, where it is already the next day", () => {
    assert.equal(formatLocalDateLabel(kickoff, TOKYO, now), "TODAY");
  });

  it("fall back to a short date further ahead", () => {
    assert.equal(formatLocalDateLabel(at("2026-11-07T15:00:00Z"), TOKYO, now), "Sun, Nov 8, 2026");
  });

  it("show a dash for a missing kick-off", () => {
    assert.equal(formatLocalDateLabel(parseFixtureDate(""), TOKYO, now), "—");
  });
});

describe("the Upcoming filter", () => {
  const now = at("2026-11-01T01:00:00Z");
  const earlier = at("2026-10-31T16:00:00Z");

  it("keeps a match from earlier today on the viewer's calendar", () => {
    assert.equal(isUpcomingLocal(earlier, LOS_ANGELES, now), true);
    assert.equal(isUpcomingLocal(earlier, TOKYO, now), true);
  });

  it("drops the same match once the viewer's day has moved on", () => {
    assert.equal(isUpcomingLocal(earlier, LONDON, now), false);
  });

  it("keeps a future match and drops an invalid date", () => {
    assert.equal(isUpcomingLocal(at("2026-11-07T15:00:00Z"), LONDON, now), true);
    assert.equal(isUpcomingLocal(at("not a date"), LONDON, now), false);
  });
});

describe("kick-off time", () => {
  it("shows the zone abbreviation", () => {
    const kickoff = at("2026-11-07T17:30:00Z");
    assert.equal(plain(formatLocalTime(kickoff, LOS_ANGELES)), "9:30 AM PST");
    assert.equal(plain(formatLocalTime(kickoff, NEW_YORK)), "12:30 PM EST");
    assert.equal(plain(formatLocalTime(kickoff, "UTC")), "5:30 PM UTC");
    assert.equal(plain(formatLocalTime(kickoff, TOKYO)), "2:30 AM GMT+9");
  });

  it("follows daylight saving", () => {
    assert.equal(plain(formatLocalTime(at("2026-07-04T17:30:00Z"), LOS_ANGELES)), "10:30 AM PDT");
  });

  it("gives the long date on the viewer's calendar", () => {
    assert.equal(formatLocalDateLong(at("2026-11-01T02:00:00Z"), LOS_ANGELES), "Saturday, October 31, 2026");
    assert.equal(formatLocalDateLong(at("2026-11-01T02:00:00Z"), TOKYO), "Sunday, November 1, 2026");
  });
});

describe("the daily limit reset", () => {
  it("is the next 00:00 UTC", () => {
    assert.equal(nextDailyReset(at("2026-10-31T23:59:59Z")).toISOString(), "2026-11-01T00:00:00.000Z");
  });

  it("moves to the next day exactly at midnight UTC", () => {
    assert.equal(nextDailyReset(at("2026-11-01T00:00:00Z")).toISOString(), "2026-11-02T00:00:00.000Z");
  });

  it("rolls over a year", () => {
    assert.equal(nextDailyReset(at("2026-12-31T12:00:00Z")).toISOString(), "2027-01-01T00:00:00.000Z");
  });

  it("is later today in Los Angeles before 5 PM", () => {
    assert.equal(plain(formatDailyReset(LOS_ANGELES, at("2026-10-31T20:00:00Z"))), "today at 5:00 PM PDT");
  });

  it("is tomorrow in Los Angeles after the reset, in tomorrow's offset", () => {
    assert.equal(plain(formatDailyReset(LOS_ANGELES, at("2026-11-01T02:00:00Z"))), "tomorrow at 4:00 PM PST");
  });

  it("is in the viewer's time in Tokyo", () => {
    assert.equal(plain(formatDailyReset(TOKYO, at("2026-10-31T20:00:00Z"))), "today at 9:00 AM GMT+9");
  });

  it("is midnight tomorrow for a viewer on UTC", () => {
    assert.equal(plain(formatDailyReset("UTC", at("2026-10-31T20:00:00Z"))), "tomorrow at 12:00 AM UTC");
  });
});

describe("with no zone passed, as in the app", () => {
  const original = process.env.TZ;
  after(() => {
    if (original === undefined) delete process.env.TZ;
    else process.env.TZ = original;
  });

  it("uses the viewer's own zone", () => {
    process.env.TZ = TOKYO;
    assert.equal(toLocalDateStr(at("2026-11-01T02:00:00Z")), "2026-11-01");
    assert.equal(plain(formatLocalTime(at("2026-11-07T17:30:00Z"))), "2:30 AM GMT+9");
    assert.equal(todayLocal(undefined, at("2026-10-31T20:00:00Z")), "2026-11-01");
  });
});
