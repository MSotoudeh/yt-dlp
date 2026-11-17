// YTDLP Digital Concert Hall bridge (Manifest V3 service worker).
//
// Job: when the local native host asks, read the signed-in site's own access token from the
// Digital Concert Hall tab's localStorage and hand it straight back over the native-messaging
// pipe. The token is never logged, stored, displayed, put on the clipboard or sent to a network.
// Only https://www.digitalconcerthall.com/* is accessible (host_permissions), and only the native
// host "com.ytdlp_tool.dch" (restricted to this extension by its manifest) can receive answers.

const HOST = 'com.ytdlp_tool.dch';
const SITE = 'https://www.digitalconcerthall.com/*';
const PAGE = /^https:\/\/www\.digitalconcerthall\.com\/[a-z]{2,3}\/(?:film|concert|work)\/\d+(?:-\d+)?\/?(?:[?#].*)?$/;
const KEY = 'access_token_production';

let port = null;

function connect() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (_) {
    port = null;
    return;
  }
  port.onMessage.addListener(onHostMessage);
  port.onDisconnect.addListener(() => {
    void chrome.runtime.lastError; // host not installed / browser closing: retried by the alarm
    port = null;
  });
}

function normalize(url) {
  try {
    const u = new URL(url);
    return u.origin + u.pathname.replace(/\/$/, '');
  } catch (_) {
    return '';
  }
}

async function pickTab(requestedUrl) {
  const tabs = await chrome.tabs.query({ url: SITE });
  if (tabs.length === 0) {
    throw new Error('No Digital Concert Hall tab is open in this browser. Open the site and sign in.');
  }
  if (requestedUrl) {
    // The token belongs to the account, not the page: prefer the matching tab, accept any signed-in tab.
    const wanted = normalize(requestedUrl);
    return tabs.find((t) => normalize(t.url) === wanted) || tabs[0];
  }
  const pages = tabs.filter((t) => PAGE.test(t.url || ''));
  if (pages.length === 1) return pages[0];
  const active = pages.filter((t) => t.active);
  if (active.length === 1) return active[0];
  if (pages.length === 0) {
    throw new Error('No concert, film or work page is open. Open the one to download, or give its URL.');
  }
  throw new Error(`${pages.length} concert pages are open; say which one by giving its URL.`);
}

async function readToken(tab) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (key) => window.localStorage.getItem(key),
    args: [KEY],
  });
  let value = result && result.result;
  if (typeof value !== 'string' || value === '') return null;
  if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
  return value;
}

async function onHostMessage(message) {
  if (!message || message.type !== 'get_token') return;
  const reply = { id: message.id };
  try {
    const tab = await pickTab(typeof message.url === 'string' ? message.url : null);
    const token = await readToken(tab);
    if (!token) {
      reply.error = 'Not signed in to Digital Concert Hall in this browser (no access token found).';
    } else {
      reply.token = token;
      reply.url = tab.url;
    }
  } catch (error) {
    reply.error = String(error && error.message ? error.message : error).slice(0, 200);
  }
  if (port) port.postMessage(reply);
}

chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('reconnect', { periodInMinutes: 1 });
  connect();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'reconnect') connect();
});
connect();
