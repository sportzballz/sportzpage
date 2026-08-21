function handler(event) {
  var request = event.request;
  var uri = request.uri;

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
