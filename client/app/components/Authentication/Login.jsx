import React from 'react';
import { Grid, Row, Col, Panel, Button } from 'react-bootstrap';
import { Router, Route, Link, History } from 'react-router-dom';

class Login extends React.Component {
    render() {
        this.props.auth.login();
        return (
            <div className="block-center mt-xl wd-xl">

            </div>
        );
    }

}

export default Login;
