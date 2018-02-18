import React from 'react';
import {Col, Row, Panel} from 'react-bootstrap';
import {withRouter} from "react-router-dom";


class StoreImageProcessors extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }


    render() {

        return (
            <div>
                <br/>
                <Row>
                    <Panel header="Store Image Processors">
                        <Row>
                            <Col lg={6}>
                                <p>To be implemented later</p>
                            </Col>
                        </Row>
                    </Panel>
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreImageProcessors);


