import Auth0Lock from '../../node_modules/auth0-lock';
import {AUTH_CONFIG} from './auth0-variables';
import axios from 'axios';
import {Redirect} from 'react-router-dom'

export default class Auth {
    constructor() {
        this.lock = new Auth0Lock(AUTH_CONFIG.clientId, AUTH_CONFIG.domain, {
            autoclose: true,
            autoParseHash: true,
            auth: {
                redirectUrl: AUTH_CONFIG.callbackUrl,
                responseType: 'token id_token',
                audience: `https://${AUTH_CONFIG.domain}/userinfo`,
                params: {
                    scope: 'openid'
                }
            },
            theme: {
                logo: '/img/logo-auth0.png'
            }
        });

        // Set the default url - todo, this needs to be moved somewhere else
        axios.defaults.baseURL = 'http://localhost:1806/';

        // For development builds, we add 150ms onto response times so that it doesn't appear unnaturally instant
        axios.interceptors.response.use(function (response) {
            return new Promise((resolve, reject) => setTimeout(resolve.bind(null, response), 250));
        }, function (error) {
            return new Promise((resolve, reject) => setTimeout(reject.bind(null, error), 250));
        });

        this.handleAuthentication();

        // binds functions to keep this context
        this.login = this.login.bind(this);
        this.logout = this.logout.bind(this);
        this.isAuthenticated = this.isAuthenticated.bind(this);
        this.authPromises = [];

        if(this.isAuthenticated())
        {
            const token = localStorage.getItem('access_token');
            axios.defaults.headers.common['Authorization'] = "Bearer " + token;
        }
        else {
            axios.defaults.headers.common['Authorization'] = "";
        }

    }

    login() {
        // Call the show method to display the widget.
        this.lock.show();
    }

    handleAuthentication() {
        // Add a callback for Lock's `authenticated` event
        this.lock.on('authenticated', (authResult) => {
            this.setSession(authResult);
            this.authPromises.forEach((promise) =>
            {
                promise.resolve();
            });
            this.authPromises = [];
        });

        // Add a callback for Lock's `authorization_error` event
        this.lock.on('authorization_error', (err) => {
            this.authPromises.forEach((promise) =>
            {
                promise.reject(err);
            });
            this.authPromises = [];
            alert(`Error: ${err.error}. Check the console for further details.`);
        });
    }

    get authPromise() {
        const authPromise = new Promise((resolve, reject) =>
        {
            this.authPromises.push({resolve, reject})
        });
        return authPromise;
    }

    setSession(authResult) {
        if (authResult && authResult.accessToken && authResult.idToken) {
            // Set the time that the access token will expire at
            let expiresAt = JSON.stringify((authResult.expiresIn * 1000) + new Date().getTime());
            localStorage.setItem('access_token', authResult.accessToken);
            localStorage.setItem('id_token', authResult.idToken);
            localStorage.setItem('expires_at', expiresAt);

            axios.defaults.headers.common['Authorization'] = "Bearer " + localStorage.getItem('access_token');
        }
    }

    logout() {
        // Clear access token and ID token from local storage
        localStorage.removeItem('access_token');
        localStorage.removeItem('id_token');
        localStorage.removeItem('expires_at');
        axios.defaults.headers.common['Authorization'] = "";
    }

    isAuthenticated() {
        // Check whether the current time is past the
        // access token's expiry time
        let expiresAt = JSON.parse(localStorage.getItem('expires_at'));
        return new Date().getTime() < expiresAt;
    }
}