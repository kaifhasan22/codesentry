import test from 'node:test'
import assert from 'node:assert/strict'
import { isSupportedGithubUrl } from '../src/lib/githubUrl.js'

test('frontend accepts supported www and canonical GitHub URLs', () => {
  for (const url of ['https://github.com/psf/requests','https://www.github.com/PSF/Requests.git/']) {
    assert.equal(isSupportedGithubUrl(url), true, url)
  }
})

test('frontend rejects schemes, hosts, ports and traversal rejected by the API', () => {
  for (const url of ['http://github.com/a/b','https://github.com:443/a/b','https://github.com.evil/a/b','https://user@github.com/a/b','https://github.com/a/..','https://github.com/a/-repo','https://github.com/a/b\n','https://github.com/%61/b','https://github.com/a/b?x=1']) {
    assert.equal(isSupportedGithubUrl(url), false, url)
  }
})
