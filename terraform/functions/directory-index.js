function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri === '/football' || uri.startsWith('/football/')) {
    return {
      statusCode: 302,
      statusDescription: 'Subscription Required',
      headers: {
        location: { value: '/subscribe/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri === '/favicon.ico') {
    request.uri = '/static/icons/favicon.ico';
    return request;
  }

  if (uri.startsWith('/subscriber/') || uri.startsWith('/delivery/')) {
    return {
      statusCode: 302,
      statusDescription: 'Subscription Required',
      headers: {
        location: { value: '/subscribe/' },
        'cache-control': { value: 'no-store' }
      }
    };
  }

  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.split('/').pop().includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
