import React, {Component} from 'react';
import { Redirect } from 'react-router-dom';
import loading from '../../img/loading.svg';

const AuthCallback  = React.createClass({
    getInitialState() {
        return {redirect: false};
    },

    componentDidMount() {
        this.props.auth.authPromise.then(() => {
            this.setState({'redirect': true});
        });
    },

    render() {
        const style = {
            position: 'absolute',
            display: 'flex',
            justifyContent: 'center',
            height: '100vh',
            width: '100vw',
            top: 0,
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: 'white',
        };

        return (
            !this.state.redirect ?
                <div style={style}>
                    <img src={loading} alt="loading"/>
                </div>
                :
                <Redirect
                    to={{
                        pathname: "/",
                        state: {from: this.props.location}
                    }}
                />
        );
    }
});

export default AuthCallback;

