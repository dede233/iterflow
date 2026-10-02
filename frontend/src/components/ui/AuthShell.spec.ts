import { mount } from '@vue/test-utils'
import pkg from '../../../package.json'
import { expect, it } from 'vitest'
import AuthShell from './AuthShell.vue'
it('renders the frontend package build version without a health request', () => {
  const version = pkg.version
  const wrapper = mount(AuthShell)
  expect(wrapper.get('.auth-foot').text()).toBe(`ITERFLOW / V${version}`)
  wrapper.unmount()
})
