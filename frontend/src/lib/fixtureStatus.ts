const LIVE_STATUSES = ["live", "inplay", "halftime"];
const FINISHED_STATUSES = ["finished", "ft", "aet", "pen"];

export function isLiveStatus(status: string | undefined): boolean {
  return LIVE_STATUSES.includes(status?.toLowerCase() ?? "");
}

export function isFinishedStatus(status: string | undefined): boolean {
  return FINISHED_STATUSES.includes(status?.toLowerCase() ?? "");
}
