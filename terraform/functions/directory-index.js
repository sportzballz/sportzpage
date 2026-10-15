function handler(event) {
  var request = event.request;
  var uri = request.uri;

  var archiveMatch = uri.match(/^\/archive\/(\d{4}-\d{2}-\d{2})(?:\/|$)/);
  if (archiveMatch) {
    var editionDate = Date.parse(archiveMatch[1] + 'T12:00:00Z');
    var ageInDays = Math.floor((Date.now() - editionDate) / 86400000);
    if (isNaN(editionDate) || ageInDays < 3 || ageInDays > 6) {
      return {
        statusCode: 302,
        statusDescription: 'Public Sample Window',
        headers: {
          location: { value: '/' },
          'cache-control': { value: 'no-store' }
        }
      };
    }
  }

  if (uri === '/football' || uri.startsWith('/football/')) {
    return {
      statusCode: 302,
      statusDescription: 'Preview Edition',
      headers: {
        location: { value: '/subscriber/current/football/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri === '/ncaaf' || uri.startsWith('/ncaaf/')) {
    return {
      statusCode: 302,
      statusDescription: 'Preview Edition',
      headers: {
        location: { value: '/subscriber/current/ncaaf/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri === '/nhl' || uri.startsWith('/nhl/')) {
    return {
      statusCode: 302,
      statusDescription: 'Preview Edition',
      headers: {
        location: { value: '/subscriber/current/nhl/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri === '/nba' || uri.startsWith('/nba/')) {
    return {
      statusCode: 302,
      statusDescription: 'Preview Edition',
      headers: {
        location: { value: '/subscriber/current/nba/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri === '/favicon.ico') {
    request.uri = '/static/icons/favicon.ico';
    return request;
  }

  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.split('/').pop().includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
