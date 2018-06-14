import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Grid, Row, Col, Dropdown, MenuItem} from 'react-bootstrap';

class Dashboard extends React.Component {

    render() {
        return (
            <ContentWrapper>
                <div className="content-heading">
                    Dashboard
                    <small>Welcome to Bricks Analytics</small>
                </div>
                <Row>
                    <Col xs={12} className="text-center">
                        <h2 className="text-thin">Single view content</h2>
                        <p>
                            Please callibrate
                        </p>
                    </Col>
                </Row>
            </ContentWrapper>
        );
    }
}

export default Dashboard;
